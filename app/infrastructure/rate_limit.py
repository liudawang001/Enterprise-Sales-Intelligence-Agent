from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic

TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_per_ms = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local values = redis.call('HMGET', key, 'tokens', 'timestamp')
local tokens = tonumber(values[1]) or capacity
local timestamp = tonumber(values[2]) or now_ms
tokens = math.min(capacity, tokens + math.max(0, now_ms - timestamp) * refill_per_ms)
local allowed = 0
local retry_after_ms = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
else
  retry_after_ms = math.ceil((requested - tokens) / refill_per_ms)
end
redis.call('HMSET', key, 'tokens', tokens, 'timestamp', now_ms)
redis.call('PEXPIRE', key, math.ceil((capacity / refill_per_ms) * 2))
return {allowed, retry_after_ms, tostring(tokens)}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_ms: int = 0
    remaining: float = 0


def provider_rate_key(provider: str, api_key_alias: str, operation: str) -> str:
    return f"rate:{provider}:{api_key_alias}:{operation}"


def inbound_rate_key(workspace_id: str, user_id: str, route: str) -> str:
    return f"rate:inbound:{workspace_id}:{user_id}:{route}"


class RedisTokenBucket:
    def __init__(self, client, *, fail_open: bool) -> None:
        self.client = client
        self.fail_open = fail_open

    async def acquire(self, key: str, *, capacity: int, refill_per_second: float, amount: int = 1) -> RateLimitDecision:
        try:
            now_ms = int(monotonic() * 1000)
            result = await self.client.eval(
                TOKEN_BUCKET_LUA, 1, key, capacity, refill_per_second / 1000, now_ms, amount
            )
            return RateLimitDecision(bool(int(result[0])), int(result[1]), float(result[2]))
        except Exception:
            if self.fail_open:
                return RateLimitDecision(True)
            return RateLimitDecision(False, retry_after_ms=1000)


class InMemoryTokenBucket:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, *, capacity: int, refill_per_second: float, amount: int = 1) -> RateLimitDecision:
        async with self._lock:
            now = monotonic()
            tokens, timestamp = self._buckets.get(key, (float(capacity), now))
            tokens = min(float(capacity), tokens + max(0, now - timestamp) * refill_per_second)
            if tokens >= amount:
                tokens -= amount
                self._buckets[key] = (tokens, now)
                return RateLimitDecision(True, remaining=tokens)
            retry_ms = int(((amount - tokens) / refill_per_second) * 1000) + 1
            self._buckets[key] = (tokens, now)
            return RateLimitDecision(False, retry_after_ms=retry_ms, remaining=tokens)
