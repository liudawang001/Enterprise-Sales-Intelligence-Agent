import asyncio
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.events import PostgresTaskEventRepository, TaskEvent
from app.repositories.task_repository import TaskRepository
from app.runtime.leases import PostgresExecutionCoordinator
from app.runtime.models import ExecutionRunStatus, RunAlreadyClaimedError

pytestmark = pytest.mark.integration


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return value


@pytest.mark.asyncio
async def test_postgres_lease_atomic_claim_and_fence() -> None:
    engine = create_async_engine(database_url())
    coordinator = PostgresExecutionCoordinator(async_sessionmaker(engine, expire_on_commit=False))
    thread = str(uuid4())

    async def claim(index: int):
        try:
            return await coordinator.claim(
                request_id=f"{thread}-{index}",
                thread_id=thread,
                workspace_id="integration",
                user_id="user",
                owner=f"worker-{index}",
                lease_seconds=60,
                trace_id=str(uuid4()),
            )
        except RunAlreadyClaimedError:
            return None

    values = await asyncio.gather(*(claim(index) for index in range(20)))
    assert sum(value is not None for value in values) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_expired_lease_reclaim_rejects_stale_fence() -> None:
    engine = create_async_engine(database_url())
    coordinator = PostgresExecutionCoordinator(async_sessionmaker(engine, expire_on_commit=False))
    thread = str(uuid4())
    first = await coordinator.claim(
        request_id=f"{thread}-first",
        thread_id=thread,
        workspace_id="integration",
        user_id="user",
        owner="worker-a",
        lease_seconds=0,
        trace_id=str(uuid4()),
    )
    second = await coordinator.claim(
        request_id=f"{thread}-second",
        thread_id=thread,
        workspace_id="integration",
        user_id="user",
        owner="worker-b",
        lease_seconds=60,
        trace_id=str(uuid4()),
    )
    assert second.fence_token > first.fence_token
    assert not await coordinator.can_promote(first.run_id, first.fence_token)
    assert not await coordinator.heartbeat(first.run_id, first.fence_token, 60)
    assert await coordinator.can_promote(second.run_id, second.fence_token)
    assert await coordinator.heartbeat(second.run_id, second.fence_token, 60)
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_completed_request_is_idempotent() -> None:
    engine = create_async_engine(database_url())
    coordinator = PostgresExecutionCoordinator(async_sessionmaker(engine, expire_on_commit=False))
    thread = str(uuid4())
    request_id = f"{thread}-request"
    run = await coordinator.claim(
        request_id=request_id,
        thread_id=thread,
        workspace_id="integration",
        user_id="user",
        owner="worker-a",
        lease_seconds=60,
        trace_id=str(uuid4()),
    )
    response = {"status": "COMPLETED", "task_id": str(uuid4())}
    assert await coordinator.finish(
        run.run_id,
        run.fence_token,
        ExecutionRunStatus.COMPLETED,
        response_data=response,
    )
    duplicate = await coordinator.claim(
        request_id=request_id,
        thread_id=thread,
        workspace_id="integration",
        user_id="user",
        owner="worker-b",
        lease_seconds=60,
        trace_id=str(uuid4()),
    )
    assert duplicate.run_id == run.run_id
    assert duplicate.response_data == response
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_task_event_replay_after_cursor() -> None:
    engine = create_async_engine(database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    thread = str(uuid4())
    async with session_factory() as session, session.begin():
        task = await TaskRepository(session, workspace_id="integration").create_task(
            thread,
            source_message_id=str(uuid4()),
        )
    repository = PostgresTaskEventRepository(session_factory)
    first = TaskEvent(
        task_id=task.task_id,
        task_version=task.version,
        workspace_id="integration",
        event_type="TASK_PROGRESS",
        payload={"progress": 25},
    )
    second = first.model_copy(
        update={
            "event_id": str(uuid4()),
            "event_type": "FINAL",
            "payload": {"status": "COMPLETED"},
            "created_at": first.created_at + timedelta(microseconds=1),
        }
    )
    await repository.append(first)
    await repository.append(second)
    assert await repository.after(task.task_id, first.event_id) == [second]
    await engine.dispose()
