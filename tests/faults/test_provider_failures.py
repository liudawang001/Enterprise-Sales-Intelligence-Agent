import asyncio

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.circuit_breaker import CircuitBreaker
from app.main import create_app
from app.research.models import ResearchBudget, ToolError, ToolResult, ToolStatus
from app.research.repository import InMemoryResearchRepository
from app.research.runtime import BoundedProviderRuntime, BudgetGuard

pytestmark = [pytest.mark.fault, pytest.mark.asyncio]


async def test_provider_429_retries_then_recovers() -> None:
    repository = InMemoryResearchRepository()
    runtime = BoundedProviderRuntime(
        repository,
        BudgetGuard(ResearchBudget()),
        max_retries=3,
        backoff_base=0,
    )
    calls = 0

    async def rate_limited() -> ToolResult:
        nonlocal calls
        calls += 1
        if calls < 3:
            return ToolResult(
                status=ToolStatus.FAILED,
                provider="provider",
                retryable=True,
                error=ToolError(
                    code="HTTP_429",
                    message="rate limited",
                    http_status=429,
                    retry_after_ms=1,
                ),
            )
        return ToolResult(status=ToolStatus.SUCCESS, provider="provider", data=[])

    result = await runtime.execute(
        research_run_id="run-429",
        task_id="task-429",
        query_id=None,
        provider="provider",
        operation="web_search",
        arguments={"query": "429"},
        call=rate_limited,
    )

    assert result.status == ToolStatus.SUCCESS
    assert calls == 3
    tool_run = next(iter(repository.tool_runs.values()))
    assert tool_run.retry_count == 2


async def test_provider_timeout_is_bounded_and_opens_circuit() -> None:
    repository = InMemoryResearchRepository()
    runtime = BoundedProviderRuntime(
        repository,
        BudgetGuard(ResearchBudget()),
        max_retries=1,
        backoff_base=0,
        circuit_breaker=CircuitBreaker(failure_threshold=2),
        operation_timeout_seconds=0.001,
    )
    calls = 0

    async def timeout() -> ToolResult:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return ToolResult(status=ToolStatus.SUCCESS, provider="provider", data=[])

    result = await runtime.execute(
        research_run_id="run-timeout",
        task_id="task-timeout",
        query_id=None,
        provider="provider",
        operation="web_search",
        arguments={"query": "timeout"},
        call=timeout,
    )
    blocked = await runtime.execute(
        research_run_id="run-timeout",
        task_id="task-timeout",
        query_id=None,
        provider="provider",
        operation="web_search",
        arguments={"query": "after-open"},
        call=timeout,
    )

    assert result.status == ToolStatus.FAILED
    assert result.error and result.error.code == "PROVIDER_TIMEOUT"
    assert calls == 2
    assert blocked.error and blocked.error.code == "PROVIDER_CIRCUIT_OPEN"


async def test_langfuse_observation_failure_does_not_break_chat() -> None:
    class BrokenClient:
        def start_as_current_observation(self, **_kwargs):
            raise ConnectionError("langfuse down")

    application = create_app()
    application.state.tracing.client = BrokenClient()
    response = TestClient(application).post(
        "/api/chat",
        json={"session_id": "langfuse-failure", "message": "集团V网是什么？"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
