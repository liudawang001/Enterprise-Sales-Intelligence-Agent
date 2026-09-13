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


@pytest.mark.asyncio
async def test_duplicate_active_request_is_rejected() -> None:
    coordinator = InMemoryExecutionCoordinator()
    await coordinator.claim(
        request_id="same-active",
        thread_id="thread",
        workspace_id="workspace",
        user_id="user",
        owner="a",
        lease_seconds=60,
        trace_id="trace-a",
    )

    with pytest.raises(RunAlreadyClaimedError):
        await coordinator.claim(
            request_id="same-active",
            thread_id="thread",
            workspace_id="workspace",
            user_id="user",
            owner="b",
            lease_seconds=60,
            trace_id="trace-b",
        )


@pytest.mark.asyncio
async def test_expired_duplicate_request_reclaims_run_with_new_fence() -> None:
    coordinator = InMemoryExecutionCoordinator()
    first = await coordinator.claim(
        request_id="same-expired",
        thread_id="thread",
        workspace_id="workspace",
        user_id="user",
        owner="a",
        lease_seconds=0,
        trace_id="trace-a",
    )

    reclaimed = await coordinator.claim(
        request_id="same-expired",
        thread_id="thread",
        workspace_id="workspace",
        user_id="user",
        owner="b",
        lease_seconds=60,
        trace_id="trace-b",
    )

    assert reclaimed.run_id == first.run_id
    assert reclaimed.fence_token > first.fence_token
    assert reclaimed.lease_owner == "b"
    assert not await coordinator.heartbeat(first.run_id, first.fence_token, 60)
    assert await coordinator.can_promote(reclaimed.run_id, reclaimed.fence_token)
