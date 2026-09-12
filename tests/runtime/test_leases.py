import asyncio

import pytest

from app.runtime.leases import InMemoryExecutionCoordinator
from app.runtime.models import ExecutionRunStatus, RunAlreadyClaimedError


@pytest.mark.asyncio
async def test_twenty_concurrent_claims_allow_one_active_lease() -> None:
    coordinator = InMemoryExecutionCoordinator()

    async def claim(index: int):
        try:
            return await coordinator.claim(
                request_id=f"request-{index}",
                thread_id="thread-1",
                workspace_id="workspace",
                user_id="user",
                owner=f"worker-{index}",
                lease_seconds=60,
                trace_id=f"trace-{index}",
            )
        except RunAlreadyClaimedError:
            return None

    values = await asyncio.gather(*(claim(index) for index in range(20)))
    assert sum(value is not None for value in values) == 1


@pytest.mark.asyncio
async def test_expired_worker_cannot_promote_after_reclaim() -> None:
    coordinator = InMemoryExecutionCoordinator()
    first = await coordinator.claim(
        request_id="first",
        thread_id="thread",
        workspace_id="workspace",
        user_id="user",
        owner="a",
        lease_seconds=0,
        trace_id="trace-a",
    )
    second = await coordinator.claim(
        request_id="second",
        thread_id="thread",
        workspace_id="workspace",
        user_id="user",
        owner="b",
        lease_seconds=60,
        trace_id="trace-b",
    )
    assert second.fence_token > first.fence_token
    assert not await coordinator.can_promote(first.run_id, first.fence_token)
    assert await coordinator.can_promote(second.run_id, second.fence_token)
    assert not await coordinator.finish(first.run_id, first.fence_token + 1, ExecutionRunStatus.COMPLETED)


@pytest.mark.asyncio
async def test_duplicate_completed_request_returns_original_response() -> None:
    coordinator = InMemoryExecutionCoordinator()
    run = await coordinator.claim(
        request_id="same",
        thread_id="thread",
        workspace_id="workspace",
        user_id="user",
        owner="a",
        lease_seconds=60,
        trace_id="trace",
    )
    await coordinator.finish(
        run.run_id, run.fence_token, ExecutionRunStatus.COMPLETED, response_data={"status": "COMPLETED"}
    )
    duplicate = await coordinator.claim(
        request_id="same",
        thread_id="thread",
        workspace_id="workspace",
        user_id="user",
        owner="b",
        lease_seconds=60,
        trace_id="other",
    )
    assert duplicate.run_id == run.run_id
    assert duplicate.response_data == {"status": "COMPLETED"}
