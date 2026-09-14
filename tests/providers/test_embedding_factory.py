import pytest

from app.providers.embedding.dashscope import DashScopeEmbeddingProvider
from app.providers.embedding.factory import build_embedding_provider
from app.settings.production import Settings


def test_factory_builds_dashscope_without_exposing_secret():
    settings = Settings(
        embedding_provider="dashscope",
        embedding_api_key="secret-value",
        embedding_base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
    )
    provider = build_embedding_provider(settings)
    assert isinstance(provider, DashScopeEmbeddingProvider)
    assert "secret-value" not in repr(settings.embedding_api_key)


def test_factory_rejects_incomplete_dashscope_configuration():
    settings = Settings(embedding_provider="dashscope", embedding_base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1")
    with pytest.raises(ValueError, match="EMBEDDING_API_KEY"):
        build_embedding_provider(settings)


def test_production_rejects_fake_embedding():
    with pytest.raises(ValueError, match="real embedding provider"):
        Settings(
            app_env="production",
            auth_mode="jwt",
            auth_issuer="issuer",
            auth_audience="audience",
            auth_jwks_url="https://id.example/jwks",
            graph_checkpointer="postgres",
            database_url="postgresql+asyncpg://user:strong@db.example/app",
            enterprise_provider="commercial",
            enterprise_api_base_url="https://enterprise.example",
            enterprise_api_key="key",
            map_provider="amap",
            amap_api_key="key",
            web_search_provider="tavily",
            tavily_api_key="key",
            web_fetch_provider="firecrawl",
            firecrawl_api_key="key",
            embedding_provider="fake",
        )
