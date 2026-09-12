from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.persistence.models.runtime import TaskEventRecord


class TaskEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    task_version: int
    workspace_id: str
    run_id: str | None = None
    event_type: str
    stage: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InMemoryTaskEventRepository:
    def __init__(self) -> None:
        self.events: dict[str, list[TaskEvent]] = {}
        self._condition = asyncio.Condition()

    async def append(self, event: TaskEvent) -> TaskEvent:
        async with self._condition:
            self.events.setdefault(event.task_id, []).append(deepcopy(event))
            self._condition.notify_all()
        return event

    async def after(self, task_id: str, event_id: str | None = None) -> list[TaskEvent]:
        values = self.events.get(task_id, [])
        if event_id:
            index = next((i for i, item in enumerate(values) if item.event_id == event_id), -1)
            values = values[index + 1 :]
        return deepcopy(values)


class PostgresTaskEventRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def append(self, event: TaskEvent) -> TaskEvent:
        async with self.session_factory() as session, session.begin():
            session.add(
                TaskEventRecord(
                    event_id=event.event_id,
                    task_id=event.task_id,
                    workspace_id=event.workspace_id,
                    task_version=event.task_version,
                    run_id=event.run_id,
                    event_type=event.event_type,
                    stage=event.stage,
                    payload=event.payload,
                    created_at=event.created_at,
                )
            )
        return event

    async def after(self, task_id: str, event_id: str | None = None) -> list[TaskEvent]:
        async with self.session_factory() as session:
            statement = (
                select(TaskEventRecord)
                .where(TaskEventRecord.task_id == task_id)
                .order_by(TaskEventRecord.created_at, TaskEventRecord.event_id)
            )
            records = list((await session.scalars(statement)).all())
        values = [
            TaskEvent(
                event_id=str(v.event_id),
                task_id=str(v.task_id),
                workspace_id=v.workspace_id,
                task_version=v.task_version,
                run_id=str(v.run_id) if v.run_id else None,
                event_type=v.event_type,
                stage=v.stage,
                payload=v.payload,
                created_at=v.created_at,
            )
            for v in records
        ]
        if event_id:
            index = next((i for i, item in enumerate(values) if item.event_id == event_id), -1)
            values = values[index + 1 :]
        return values


class TaskEventService:
    def __init__(self, repository, redis_client=None) -> None:
        self.repository = repository
        self.redis = redis_client

    async def publish(self, event: TaskEvent) -> TaskEvent:
        await self.repository.append(event)
        if self.redis is not None:
            try:
                await self.redis.xadd(f"task-events:{event.task_id}", {"event": event.model_dump_json()}, id="*")
            except Exception:
                pass
        return event

    async def replay(self, task_id: str, last_event_id: str | None) -> list[TaskEvent]:
        return await self.repository.after(task_id, last_event_id)
