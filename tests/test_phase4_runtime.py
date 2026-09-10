import asyncio

import pytest

from app.providers.fakes import FakeEnterpriseProvider
from app.research.models import (
    EnterpriseSearchRequest,
    ResearchBudget,
    ToolError,
    ToolResult,
    ToolStatus,
)
from app.research.repository import InMemoryResearchRepository
from app.research.runtime import (
    BoundedProviderRuntime,
    BudgetGuard,
    request_hash,
    sanitize,
)
from app.research.safety import UrlSafetyValidator, filter_public_contacts


@pytest.mark.asyncio
async def test_budget_blocks_before_provider_call_and_idempotency_reuses_success():
    repository = InMemoryResearchRepository()
    budget = ResearchBudget(max_tool_calls=1, max_enterprise_search_calls=1)
    runtime = BoundedProviderRuntime(repository, BudgetGuard(budget), backoff_base=0)
    provider = FakeEnterpriseProvider()
    request = EnterpriseSearchRequest(region="上海松江")
    kwargs = {
        "research_run_id": "run",
        "task_id": "task",
        "query_id": "query",
        "provider": provider.name,
        "operation": "enterprise_search",
        "arguments": request.model_dump(),
        "call": lambda: provider.search_companies(request),
    }
    first = await runtime.execute(**kwargs)
    second = await runtime.execute(**kwargs)
    blocked_request = EnterpriseSearchRequest(region="浦东")
    blocked = await runtime.execute(
        **{
            **kwargs,
            "arguments": blocked_request.model_dump(),
            "call": lambda: provider.search_companies(blocked_request),
        }
    )
    assert first.status == second.status == ToolStatus.SUCCESS
    assert provider.call_count == 1
    assert blocked.status == ToolStatus.BUDGET_BLOCKED


@pytest.mark.asyncio
async def test_retryable_503_retries_but_401_does_not():
    repository = InMemoryResearchRepository()
    runtime = BoundedProviderRuntime(
        repository, BudgetGuard(ResearchBudget()), max_retries=3, backoff_base=0
    )
    calls = 0

    async def transient():
        nonlocal calls
        calls += 1
        if calls < 3:
            return ToolResult(
                status=ToolStatus.FAILED,
                provider="p",
                retryable=True,
                error=ToolError(code="HTTP_503", message="busy", http_status=503),
            )
        return ToolResult(status=ToolStatus.SUCCESS, provider="p", data=[])

    result = await runtime.execute(
        research_run_id="r",
        task_id="t",
        query_id=None,
        provider="p",
        operation="web_search",
        arguments={"q": 1},
        call=transient,
    )
    assert result.status == ToolStatus.SUCCESS and calls == 3
    nonretry_calls = 0

    async def unauthorized():
        nonlocal nonretry_calls
        nonretry_calls += 1
        return ToolResult(
            status=ToolStatus.FAILED,
            provider="p",
            error=ToolError(code="HTTP_401", message="no", http_status=401),
        )

    await runtime.execute(
        research_run_id="r",
        task_id="t",
        query_id=None,
        provider="p",
        operation="web_search",
        arguments={"q": 2},
        call=unauthorized,
    )
    assert nonretry_calls == 1


@pytest.mark.asyncio
async def test_url_safety_and_public_contact_policy(monkeypatch):
    validator = UrlSafetyValidator()
    assert not (await validator.validate("http://127.0.0.1/a")).allowed
    assert not (await validator.validate("http://localhost/a")).allowed
    assert not (await validator.validate("http://169.254.169.254/a")).allowed
    assert not (await validator.validate("file:///etc/passwd")).allowed
    phones, _ = filter_public_contacts("公司总机：021-55550000 联系人：13800138000")
    assert phones == ["021-55550000"]


def test_hash_is_canonical_and_secrets_are_sanitized():
    assert request_hash("p", "op", {"b": 2, "a": 1}) == request_hash(
        "p", "op", {"a": 1, "b": 2}
    )
    assert sanitize({"Authorization": "secret", "nested": {"api_key": "key"}}) == {
        "Authorization": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]"},
    }


@pytest.mark.asyncio
async def test_provider_semaphore_limits_concurrency():
    active = maximum = 0
    runtime = BoundedProviderRuntime(
        InMemoryResearchRepository(),
        BudgetGuard(ResearchBudget()),
        concurrency={
            "web_search": 2,
            "enterprise_search": 1,
            "enterprise_profile": 1,
            "map": 1,
            "web_fetch": 1,
        },
        backoff_base=0,
    )

    async def slow():
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return ToolResult(status=ToolStatus.SUCCESS, provider="slow", data=[])

    await asyncio.gather(
        *(
            runtime.execute(
                research_run_id="r",
                task_id="t",
                query_id=None,
                provider="slow",
                operation="web_search",
                arguments={"i": i},
                call=slow,
            )
            for i in range(8)
        )
    )
    assert maximum == 2


@pytest.mark.asyncio
async def test_redirect_chain_is_revalidated(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda host, port: [
            (
                None,
                None,
                None,
                None,
                ("93.184.216.34" if host == "example.com" else "127.0.0.1", port),
            )
        ],
    )
    verdict = await UrlSafetyValidator().validate_redirects(
        ["https://example.com", "http://localhost/private"]
    )
    assert not verdict.allowed


def test_personal_email_is_filtered():
    _, emails = filter_public_contacts("sales@example.com private@gmail.com")
    assert emails == ["sales@example.com"]
