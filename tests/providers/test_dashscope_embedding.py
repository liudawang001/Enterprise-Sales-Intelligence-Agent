import json

import httpx
import pytest

from app.providers.embedding.dashscope import DashScopeEmbeddingProvider, EmbeddingProviderError


def _provider(handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return DashScopeEmbeddingProvider("test-secret", base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1", client=client, **kwargs)


def test_batches_and_reorders_text_index_without_logging_content():
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        texts = payload["input"]["texts"]
        return httpx.Response(200, json={"output": {"embeddings": [{"text_index": i, "embedding": [float(i + 1)] + [0.0] * 1023} for i in reversed(range(len(texts)))]}, "usage": {"total_tokens": len(texts)}, "request_id": "req-1"}, request=request)

    provider = _provider(handler, batch_size=2)
    vectors = provider.embed_documents(["a", "b", "c"])
    assert len(calls) == 2
    assert [payload["parameters"]["text_type"] for payload in calls] == ["document", "document"]
    assert vectors[0][0] == pytest.approx(1.0)
    assert vectors[1][0] == pytest.approx(1.0)
    assert provider.last_usage.total_tokens == 3


def test_query_contract_and_empty_documents():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"output": {"embeddings": [{"text_index": 0, "embedding": [1.0] + [0.0] * 1023}]}, "request_id": "req-2"}, request=request)

    provider = _provider(handler)
    assert provider.embed_documents([]) == []
    vector = provider.embed_query("查询")
    assert len(vector) == 1024
    assert calls[0]["parameters"] == {"text_type": "query", "dimension": 1024, "output_type": "dense"}


def test_bad_dimension_is_rejected_without_partial_result():
    def handler(request):
        return httpx.Response(200, json={"output": {"embeddings": [{"text_index": 0, "embedding": [1.0]}]}}, request=request)

    with pytest.raises(EmbeddingProviderError, match="dimension"):
        _provider(handler).embed_query("查询")
