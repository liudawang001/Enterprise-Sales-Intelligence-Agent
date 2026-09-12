from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class CacheService(Protocol):
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...


class RedisCacheService:
    def __init__(self, client) -> None:
        self.client = client

    async def get(self, key: str) -> bytes | None:
        try:
            return await self.client.get(key)
        except Exception:
            logger.warning("CACHE_UNAVAILABLE", extra={"error_code": "CACHE_UNAVAILABLE"})
            return None

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        try:
            await self.client.set(key, value, ex=ttl)
        except Exception:
            logger.warning("CACHE_UNAVAILABLE", extra={"error_code": "CACHE_UNAVAILABLE"})

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete(key)
        except Exception:
            logger.warning("CACHE_UNAVAILABLE", extra={"error_code": "CACHE_UNAVAILABLE"})


@dataclass
class _MemoryValue:
    value: bytes
    expires_at: datetime


class InMemoryCacheService:
    def __init__(self) -> None:
        self.values: dict[str, _MemoryValue] = {}

    async def get(self, key: str) -> bytes | None:
        item = self.values.get(key)
        if not item or item.expires_at <= datetime.now(UTC):
            self.values.pop(key, None)
            return None
        return item.value

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        self.values[key] = _MemoryValue(value=value, expires_at=datetime.now(UTC) + timedelta(seconds=ttl))

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class CacheKeys:
    @staticmethod
    def provider(provider: str, request_hash: str) -> str:
        return f"provider:{provider}:{request_hash}"

    @staticmethod
    def region(normalized_region: str) -> str:
        return f"region:{normalized_region}"

    @staticmethod
    def rag(knowledge_version: str, query_hash: str) -> str:
        return f"rag:{knowledge_version}:{query_hash}"

    @staticmethod
    def public_profile(enterprise_id: str, field_set_hash: str) -> str:
        return f"public_profile:{enterprise_id}:{field_set_hash}"


class ProviderCache:
    """JSON cache retaining the source retrieval timestamp verbatim."""

    def __init__(self, cache: CacheService, ttl_by_operation: dict[str, int]) -> None:
        self.cache = cache
        self.ttl_by_operation = ttl_by_operation

    async def get(self, provider: str, request_hash: str) -> dict[str, Any] | None:
        raw = await self.cache.get(CacheKeys.provider(provider, request_hash))
        return json.loads(raw) if raw else None

    async def set(self, provider: str, operation: str, request_hash: str, payload: dict[str, Any]) -> None:
        # source_retrieved_at is part of payload and is never replaced by cache_hit_at.
        value = {**deepcopy(payload), "cache_hit_at": None}
        await self.cache.set(
            CacheKeys.provider(provider, request_hash),
            json.dumps(value, ensure_ascii=False, default=str).encode(),
            self.ttl_by_operation[operation],
        )
