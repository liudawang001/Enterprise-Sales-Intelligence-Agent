import pytest

from app.infrastructure.cache import RedisCacheService
from app.infrastructure.rate_limit import RedisTokenBucket
from app.observability.tracing import LangfuseTracing
from app.settings.production import Settings


class BrokenRedis:
    async def get(self, *_args, **_kwargs):
        raise ConnectionError("redis down")

    async def set(self, *_args, **_kwargs):
        raise ConnectionError("redis down")

    async def delete(self, *_args, **_kwargs):
        raise ConnectionError("redis down")

    async def eval(self, *_args, **_kwargs):
        raise ConnectionError("redis down")


@pytest.mark.fault
@pytest.mark.asyncio
async def test_redis_cache_fails_open_and_provider_limiter_fails_safe() -> None:
    cache = RedisCacheService(BrokenRedis())
    assert await cache.get("provider:test:hash") is None
    await cache.set("provider:test:hash", b"value", 60)
    assert (
        await RedisTokenBucket(BrokenRedis(), fail_open=True).acquire("key", capacity=1, refill_per_second=1)
    ).allowed
    assert not (
        await RedisTokenBucket(BrokenRedis(), fail_open=False).acquire("key", capacity=1, refill_per_second=1)
    ).allowed


@pytest.mark.fault
@pytest.mark.asyncio
async def test_langfuse_shutdown_failure_does_not_escape(caplog) -> None:
    class BrokenClient:
        def flush(self):
            raise ConnectionError("langfuse down")

        def shutdown(self):
            raise AssertionError("not reached")

    tracing = LangfuseTracing(Settings())
    tracing.client = BrokenClient()
    await tracing.close()
    assert "OBSERVABILITY_UNAVAILABLE" in caplog.text
