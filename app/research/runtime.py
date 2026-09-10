from __future__ import annotations

import asyncio
import hashlib
import json
import random
from collections import defaultdict
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from app.research.models import (
    ResearchBudget,
    ToolError,
    ToolResult,
    ToolRun,
    ToolStatus,
)
from app.research.repository import InMemoryResearchRepository

LIMIT_FIELDS = {
    "enterprise_search": "max_enterprise_search_calls",
    "enterprise_profile": "max_enterprise_profile_calls",
    "map": "max_map_calls",
    "web_search": "max_web_search_calls",
    "web_fetch": "max_web_fetch_calls",
}


class BudgetGuard:
    def __init__(self, budget: ResearchBudget) -> None:
        self.budget = budget
        self.used: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self.started_at = monotonic()

    async def reserve(self, operation: str, amount: int = 1) -> bool:
        async with self._lock:
            if monotonic() - self.started_at >= self.budget.max_runtime_seconds:
                return False
            field = LIMIT_FIELDS[operation]
            if self.used[
                "tool_calls"
            ] + amount > self.budget.max_tool_calls or self.used[
                operation
            ] + amount > getattr(self.budget, field):
                return False
            if (
                operation == "web_fetch"
                and self.used["web_pages"] + amount > self.budget.max_web_pages
            ):
                return False
            self.used["tool_calls"] += amount
            self.used[operation] += amount
            if operation == "web_fetch":
                self.used["web_pages"] += amount
            return True


def sanitize(value: Any) -> Any:
    secret_keys = {"api_key", "apikey", "authorization", "cookie", "token", "password"}
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if k.lower() in secret_keys else sanitize(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


def request_hash(provider: str, operation: str, arguments: Any) -> str:
    canonical = json.dumps(
        arguments,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(f"{provider}:{operation}:{canonical}".encode()).hexdigest()


class BoundedProviderRuntime:
    def __init__(
        self,
        repository: InMemoryResearchRepository,
        guard: BudgetGuard,
        *,
        max_retries: int = 3,
        concurrency: dict[str, int] | None = None,
        cache_ttl_seconds: dict[str, int] | None = None,
        backoff_base: float = 0.01,
    ) -> None:
        self.repository, self.guard, self.max_retries, self.backoff_base = (
            repository,
            guard,
            max_retries,
            backoff_base,
        )
        values = concurrency or {
            "enterprise_search": 5,
            "enterprise_profile": 5,
            "map": 5,
            "web_search": 8,
            "web_fetch": 4,
        }
        self.semaphores = {
            key: asyncio.Semaphore(value) for key, value in values.items()
        }
        self.cache_ttl_seconds = cache_ttl_seconds or {
            "enterprise_search": 86400,
            "enterprise_profile": 604800,
            "map": 86400,
            "web_search": 21600,
            "web_fetch": 86400,
        }

    async def execute(
        self,
        *,
        research_run_id: str,
        task_id: str,
        query_id: str | None,
        provider: str,
        operation: str,
        arguments: dict[str, Any],
        call: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
        digest = request_hash(provider, operation, arguments)
        cached = self.repository.find_successful_tool_run(
            digest, self.cache_ttl_seconds.get(operation)
        )
        if cached and cached.result:
            return cached.result
        result: ToolResult | None = None
        retry_count = 0
        async with self.semaphores[operation]:
            for attempt in range(self.max_retries + 1):
                if not await self.guard.reserve(operation):
                    result = ToolResult(
                        status=ToolStatus.BUDGET_BLOCKED,
                        provider=provider,
                        error=ToolError(
                            code="BUDGET_EXHAUSTED", message="Research budget exhausted"
                        ),
                    )
                    break
                result = await call()
                if (
                    result.status in {ToolStatus.SUCCESS, ToolStatus.EMPTY}
                    or not result.retryable
                ):
                    retry_count = attempt
                    break
                retry_count = attempt
                if attempt < self.max_retries:
                    delay = (
                        (result.error.retry_after_ms / 1000)
                        if result.error and result.error.retry_after_ms
                        else self.backoff_base * (2**attempt)
                        + random.uniform(0, self.backoff_base)
                    )
                    await asyncio.sleep(delay)
        assert result is not None
        self.repository.save_tool_run(
            ToolRun(
                research_run_id=research_run_id,
                task_id=task_id,
                query_id=query_id,
                tool_name=operation,
                provider=provider,
                request_hash=digest,
                request_summary=sanitize(arguments),
                status=result.status,
                latency_ms=result.latency_ms,
                retry_count=retry_count,
                error_code=result.error.code if result.error else None,
                result=result,
            )
        )
        return result
