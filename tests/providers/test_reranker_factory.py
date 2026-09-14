import pytest

from app.knowledge.rerank.dashscope import DashScopeReranker
from app.knowledge.rerank.factory import build_reranker
from app.settings.production import Settings


def test_factory_builds_dashscope_reranker():
    settings = Settings(
        reranker_provider="dashscope",
        reranker_model="qwen3-rerank",
        reranker_api_key="secret-value",
        reranker_base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
    )
    provider = build_reranker(settings)
    assert isinstance(provider, DashScopeReranker)
    assert provider.profile_version == "qwen3-rerank:v1"


def test_factory_honors_reranker_profile_override():
    settings = Settings(
        reranker_provider="dashscope",
        reranker_model="qwen3-rerank",
        reranker_api_key="secret-value",
        reranker_base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
        rag_reranker_profile="qwen3-rerank:canary",
    )
    assert build_reranker(settings).profile_version == "qwen3-rerank:canary"
    assert "secret-value" not in repr(settings.reranker_api_key)


def test_read_profile_takes_precedence_during_rollout():
    settings = Settings(
        reranker_provider="dashscope",
        reranker_model="qwen3-rerank",
        reranker_api_key="secret-value",
        reranker_base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
        rag_reranker_profile="qwen3-rerank:v1",
        rag_reranker_read_profile="qwen3-rerank:canary",
    )
    assert build_reranker(settings).profile_version == "qwen3-rerank:canary"


def test_factory_rejects_incomplete_dashscope_configuration():
    settings = Settings(reranker_provider="dashscope", reranker_model="qwen3-rerank", reranker_base_url="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1")
    with pytest.raises(ValueError, match="RERANKER_API_KEY"):
        build_reranker(settings)
