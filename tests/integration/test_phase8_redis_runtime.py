import asyncio
import os
from uuid import uuid4

import pytest

from app.infrastructure.events import InMemoryTaskEventRepository, TaskEvent, TaskEventService
from app.infrastructure.rate_limit import RedisTokenBucket
from app.infrastructure.redis import RedisManager

pytestmark = pytest.mark.integration


def redis_url() -> str:
    value = os.getenv("TEST_REDIS_URL")
    if not value:
        pytest.skip("TEST_REDIS_URL is not configured")
    return value


@pytest.mark.asyncio
async def test_redis_token_bucket_is_atomic_under_concurrency() -> None:
    manager = RedisManager(redis_url())
    client = await manager.start()
    key = f"test:rate:{uuid4()}"
    try:
        limiter = RedisTokenBucket(client, fail_open=False)
        decisions = await asyncio.gather(
            *(limiter.acquire(key, capacity=5, refill_per_second=0.0001) for _ in range(40))
        )
        assert sum(item.allowed for item in decisions) == 5
    finally:
        await client.delete(key)
        await manager.close()


@pytest.mark.asyncio
async def test_task_event_is_durable_before_redis_stream_publish() -> None:
    manager = RedisManager(redis_url())
    client = await manager.start()
    task_id = str(uuid4())
    stream = f"task-events:{task_id}"
    repository = InMemoryTaskEventRepository()
    service = TaskEventService(repository, client)
    event = TaskEvent(
        task_id=task_id,
        task_version=1,
        workspace_id="integration",
        event_type="TASK_PROGRESS",
        payload={"progress": 50},
    )
    try:
        await service.publish(event)
        persisted = await service.replay(task_id, None)
        streamed = await client.xrange(stream)
        assert persisted == [event]
        assert len(streamed) == 1
        assert TaskEvent.model_validate_json(streamed[0][1][b"event"]) == event
    finally:
        await client.delete(stream)
        await manager.close()
