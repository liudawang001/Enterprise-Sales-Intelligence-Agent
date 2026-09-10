from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.enums import TaskStage, TaskStatus
from app.domain.task import LeadTask, TaskPatch
from app.mutation.preview import apply_patch_pure
from app.persistence.models.task import LeadTaskRecord, LeadTaskVersionRecord
from app.repositories.mock_task_repository import (
    MockTaskRepository,
    TaskVersionConflictError,
)
from app.tasks.models import TaskVersion

InMemoryTaskRepository = MockTaskRepository


class TaskRepository:
    """PostgreSQL adapter with immutable versions and an optimistic version fence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_task(self, thread_id: str, source_message_id: str | None = None) -> LeadTask:
        if source_message_id:
            existing = await self.session.scalar(select(LeadTaskVersionRecord).join(LeadTaskRecord, LeadTaskRecord.id == LeadTaskVersionRecord.task_id).where(LeadTaskRecord.thread_id == thread_id, LeadTaskVersionRecord.source_message_id == source_message_id))
            if existing:
                return await self.get_task(str(existing.task_id))  # type: ignore[return-value]
        now = datetime.now(UTC)
        task = LeadTask(task_id=str(uuid4()), session_id=thread_id, stage=TaskStage.COLLECTING_REQUIREMENTS, status=TaskStatus.RUNNING, source_message_id=source_message_id, created_at=now, updated_at=now)
        self.session.add(LeadTaskRecord(id=UUID(task.task_id), thread_id=thread_id, business_code=None, active_version=1, stage=task.stage.value, status=task.status.value, is_active=True, created_at=now, updated_at=now))
        await self.session.execute(update(LeadTaskRecord).where(LeadTaskRecord.thread_id == thread_id, LeadTaskRecord.id != UUID(task.task_id)).values(is_active=False))
        self.session.add(self._version_record(TaskVersion.from_task(task)))
        await self.session.flush()
        return task

    async def get_task(self, task_id: str) -> LeadTask | None:
        head = await self.session.get(LeadTaskRecord, UUID(task_id))
        if not head:
            return None
        version = await self.session.scalar(select(LeadTaskVersionRecord).where(LeadTaskVersionRecord.task_id == head.id, LeadTaskVersionRecord.version == head.active_version))
        return self._to_task(head, version) if version else None

    async def get_active_task(self, thread_id: str) -> LeadTask | None:
        head = await self.session.scalar(select(LeadTaskRecord).where(LeadTaskRecord.thread_id == thread_id, LeadTaskRecord.is_active.is_(True)).order_by(LeadTaskRecord.updated_at.desc()))
        return await self.get_task(str(head.id)) if head else None

    async def list_tasks(self, thread_id: str | None = None) -> list[LeadTask]:
        statement = select(LeadTaskRecord).order_by(LeadTaskRecord.created_at)
        if thread_id:
            statement = statement.where(LeadTaskRecord.thread_id == thread_id)
        heads = list((await self.session.scalars(statement)).all())
        return [task for head in heads if (task := await self.get_task(str(head.id)))]

    async def activate_task(self, thread_id: str, task_id: str) -> LeadTask:
        task = await self.get_task(task_id)
        if not task or task.session_id != thread_id:
            raise KeyError("TASK_NOT_FOUND")
        await self.session.execute(update(LeadTaskRecord).where(LeadTaskRecord.thread_id == thread_id).values(is_active=False))
        await self.session.execute(update(LeadTaskRecord).where(LeadTaskRecord.id == UUID(task_id)).values(is_active=True, updated_at=datetime.now(UTC)))
        await self.session.flush()
        return task

    async def apply_patch(self, task_id: str, patch: TaskPatch, *, base_version: int, mutation_id: str | None = None, source_message_id: str | None = None) -> LeadTask:
        head = await self.session.scalar(select(LeadTaskRecord).where(LeadTaskRecord.id == UUID(task_id)).with_for_update())
        if not head:
            raise KeyError("TASK_NOT_FOUND")
        if head.active_version != base_version:
            raise TaskVersionConflictError(task_id, base_version, head.active_version)
        task = await self.get_task(task_id)
        prospective = apply_patch_pure(task, patch)  # type: ignore[arg-type]
        version = TaskVersion.from_task(prospective, parent_version=base_version, mutation_id=mutation_id, source_message_id=source_message_id)
        self.session.add(self._version_record(version))
        head.active_version = prospective.version
        head.business_code = prospective.business
        head.stage = prospective.stage.value
        head.status = prospective.status.value
        head.updated_at = datetime.now(UTC)
        await self.session.flush()
        return prospective

    async def list_versions(self, task_id: str) -> list[TaskVersion]:
        records = list((await self.session.scalars(select(LeadTaskVersionRecord).where(LeadTaskVersionRecord.task_id == UUID(task_id)).order_by(LeadTaskVersionRecord.version))).all())
        return [self._to_version(item) for item in records]

    @staticmethod
    def _version_record(value: TaskVersion) -> LeadTaskVersionRecord:
        return LeadTaskVersionRecord(id=UUID(value.version_id), task_id=UUID(value.task_id), version=value.version, parent_version=value.parent_version, business_code=value.business, region=value.region, target_count=value.target_count, constraints_json=value.constraints, required_fields=value.required_fields, export_fields=value.export_fields, source_message_id=value.source_message_id, mutation_id=UUID(value.mutation_id) if value.mutation_id else None, created_at=value.created_at)

    @staticmethod
    def _to_version(value: LeadTaskVersionRecord) -> TaskVersion:
        return TaskVersion(version_id=str(value.id), task_id=str(value.task_id), version=value.version, parent_version=value.parent_version, business=value.business_code, region=value.region, target_count=value.target_count, constraints=value.constraints_json, required_fields=value.required_fields, export_fields=value.export_fields, source_message_id=value.source_message_id, mutation_id=str(value.mutation_id) if value.mutation_id else None, created_at=value.created_at)

    @classmethod
    def _to_task(cls, head: LeadTaskRecord, version: LeadTaskVersionRecord) -> LeadTask:
        return LeadTask(task_id=str(head.id), session_id=head.thread_id, business=version.business_code, region=version.region, target_count=version.target_count, constraints=version.constraints_json, required_fields=version.required_fields, export_fields=version.export_fields, stage=TaskStage(head.stage), status=TaskStatus(head.status), version=head.active_version, source_message_id=version.source_message_id, created_at=head.created_at, updated_at=head.updated_at)
