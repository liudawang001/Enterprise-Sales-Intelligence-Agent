import os

import pytest

from app.providers.embedding.factory import build_embedding_provider
from app.settings.production import Settings


@pytest.mark.external
@pytest.mark.asyncio
async def test_real_dashscope_embedding_smoke():
    key = os.getenv("EMBEDDING_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("EMBEDDING_BASE_URL")
    if not key or not base_url:
        pytest.skip("EMBEDDING_API_KEY/DASHSCOPE_API_KEY and EMBEDDING_BASE_URL are required")
    settings = Settings(
        embedding_provider="dashscope",
        embedding_model="qwen3.7-text-embedding",
        embedding_api_key=key,
        embedding_base_url=base_url,
    )
    provider = build_embedding_provider(settings)
    vector = await provider.aembed_query("企业专线办理条件")
    assert len(vector) == 1024
    assert provider.last_usage.total_tokens >= 0
