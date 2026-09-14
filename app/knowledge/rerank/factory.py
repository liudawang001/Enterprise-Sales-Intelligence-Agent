from __future__ import annotations

from typing import Any

from app.knowledge.rerank.bge import BGEReranker
from app.knowledge.rerank.dashscope import DashScopeReranker
from app.knowledge.rerank.fake import FakeReranker


def build_reranker(settings: Any):
    provider = str(settings.reranker_provider).lower()
    if provider == "fake":
        if settings.app_env.lower() in {"production", "prod"}:
            raise ValueError("FAKE_RERANKER_FORBIDDEN_IN_PRODUCTION")
        return FakeReranker()
    if provider == "dashscope":
        return DashScopeReranker(
            settings.reranker_api_key_value,
            model=settings.reranker_model,
            base_url=settings.reranker_base_url,
            timeout_seconds=settings.reranker_timeout_seconds,
            connect_timeout_seconds=settings.reranker_connect_timeout_seconds,
            max_retries=settings.reranker_max_retries,
            return_documents=settings.reranker_return_documents,
            max_candidates=settings.reranker_max_candidates,
            max_document_chars=settings.reranker_max_document_chars,
            profile_version=settings.reranker_profile_version,
        )
    if provider == "bge":
        return BGEReranker(model_name=settings.reranker_model)
    raise ValueError("RERANKER_PROVIDER_CONFIGURATION_INVALID")
