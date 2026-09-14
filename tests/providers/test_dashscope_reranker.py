import json

import httpx
import pytest

from app.knowledge.retrieval.models import RetrievalHit
from app.knowledge.rerank.dashscope import DashScopeReranker, RerankerProviderError


def _hit(index: int, content: str) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=f"chunk-{index}",
        document_id="doc-1",
        content=content,
        page_start=index + 1,
        page_end=index + 1,
        metadata={"document_title": "Demo"},
    )


def _provider(handler, **kwargs):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DashScopeReranker(
        "test-secret",
        base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
        async_client=client,
        **kwargs,
    ), client


def _sync_provider(handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return DashScopeReranker(
        "test-secret",
        base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
        client=client,
        **kwargs,
    ), client


@pytest.mark.asyncio
async def test_request_contract_maps_unordered_indices_and_scores():
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(
            200,
            json={
                "output": {"results": [{"index": 1, "relevance_score": 0.2}, {"index": 0, "relevance_score": 0.9}]},
                "usage": {"total_tokens": 12},
                "request_id": "req-1",
            },
            request=request,
        )

    provider, client = _provider(handler)
    try:
        hits = [_hit(0, "irrelevant"), _hit(1, "relevant")]
        ranked = await provider.rerank("query", hits, top_k=2)
    finally:
        await client.aclose()
    assert [hit.chunk_id for hit in ranked] == ["chunk-0", "chunk-1"]
    assert ranked[0].rerank_score == pytest.approx(0.9)
    assert calls[0]["model"] == "qwen3-rerank"
    assert calls[0]["input"]["query"] == "query"
    assert calls[0]["input"]["documents"] == ["irrelevant", "relevant"]
    assert calls[0]["parameters"] == {"top_n": 2, "return_documents": False}
    assert provider.last_usage.total_tokens == 12


@pytest.mark.asyncio
async def test_empty_candidates_do_not_call_remote():
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={"output": {"results": []}}, request=request)

    provider, client = _provider(handler)
    try:
        assert await provider.rerank("query", [], top_k=3) == []
    finally:
        await client.aclose()
    assert called is False


@pytest.mark.asyncio
async def test_429_retries_and_protocol_errors_are_rejected():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"code": "Throttled"}, headers={"Retry-After": "0"}, request=request)
        return httpx.Response(200, json={"output": {"results": [{"index": 0, "relevance_score": 0.8}]}}, request=request)

    provider, client = _provider(handler, max_retries=1)
    try:
        assert len(await provider.rerank("query", [_hit(0, "text")], top_k=1)) == 1
    finally:
        await client.aclose()
    assert attempts == 2

    def invalid_handler(request):
        return httpx.Response(200, json={"output": {"results": [{"index": 4, "relevance_score": 0.8}]}}, request=request)

    invalid, client = _provider(invalid_handler, max_retries=0)
    try:
        invalid_hit = _hit(0, "text")
        with pytest.raises(RerankerProviderError, match="index"):
            await invalid.rerank("query", [invalid_hit], top_k=1)
        assert invalid_hit.rerank_score is None
    finally:
        await client.aclose()


def test_sync_facade_and_request_budget_preserve_metadata():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"output": {"results": [{"index": 0, "relevance_score": 0.7}]}, "request_id": "sync-1"},
            request=request,
        )

    provider, client = _sync_provider(handler, max_candidates=1, max_document_chars=5, return_documents=True)
    try:
        hit = _hit(0, "abcdefghij")
        ranked = provider.rerank_sync("query", [hit, _hit(1, "second")], top_k=1)
    finally:
        client.close()
    assert ranked[0].chunk_id == "chunk-0"
    assert ranked[0].metadata == {"document_title": "Demo"}
    assert calls[0]["input"]["documents"] == ["abcde"]
    assert calls[0]["parameters"] == {"top_n": 1, "return_documents": True}
