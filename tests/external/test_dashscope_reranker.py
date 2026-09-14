import os

import pytest

from app.knowledge.rerank.factory import build_reranker
from app.knowledge.retrieval.models import RetrievalHit
from app.settings.production import Settings


@pytest.mark.external
@pytest.mark.asyncio
async def test_real_dashscope_reranker_smoke():
    key = os.getenv("RERANKER_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("RERANKER_BASE_URL")
    if not key or not base_url:
        pytest.skip("RERANKER_API_KEY/DASHSCOPE_API_KEY and RERANKER_BASE_URL are required")
    settings = Settings(
        reranker_provider="dashscope",
        reranker_model=os.getenv("RERANKER_MODEL", "qwen3-rerank"),
        reranker_api_key=key,
        reranker_base_url=base_url,
    )
    provider = build_reranker(settings)
    hits = [
        RetrievalHit(chunk_id="positive", document_id="doc", content="企业专线适合企业客户。", page_start=1, page_end=1, metadata={}),
        RetrievalHit(chunk_id="negative", document_id="doc", content="这是天气信息。", page_start=1, page_end=1, metadata={}),
    ]
    ranked = await provider.rerank("企业专线适合什么客户？", hits, top_k=2)
    assert ranked[0].chunk_id == "positive"
    assert provider.last_usage.total_tokens >= 0
