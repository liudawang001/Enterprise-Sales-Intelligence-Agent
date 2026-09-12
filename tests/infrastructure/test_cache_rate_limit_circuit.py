import asyncio
from datetime import UTC, datetime

import pytest

from app.infrastructure.cache import InMemoryCacheService, ProviderCache
from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitState
from app.infrastructure.rate_limit import InMemoryTokenBucket


@pytest.mark.asyncio
async def test_provider_cache_keeps_source_retrieved_at() -> None:
    cache = ProviderCache(InMemoryCacheService(), {"profile": 60})
    source_time = datetime(2025, 1, 2, tzinfo=UTC).isoformat()
    await cache.set("enterprise", "profile", "hash", {"source_retrieved_at": source_time, "value": {"name": "A"}})
    hit = await cache.get("enterprise", "hash")
    assert hit["source_retrieved_at"] == source_time


@pytest.mark.asyncio
async def test_token_bucket_is_atomic_under_concurrency() -> None:
    limiter = InMemoryTokenBucket()
    decisions = await asyncio.gather(
        *(limiter.acquire("rate:provider:alias:search", capacity=5, refill_per_second=0.0001) for _ in range(40))
    )
    assert sum(item.allowed for item in decisions) == 5


@pytest.mark.asyncio
async def test_circuit_opens_and_allows_one_half_open_probe() -> None:
    breaker = CircuitBreaker(failure_threshold=2, open_seconds=0, half_open_probe_count=1)
    await breaker.failure("provider")
    await breaker.failure("provider")
    assert breaker.state("provider") == CircuitState.OPEN
    assert await breaker.allow("provider")
    assert not await breaker.allow("provider")
    await breaker.success("provider")
    assert breaker.state("provider") == CircuitState.CLOSED
