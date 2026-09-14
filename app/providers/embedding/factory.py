from __future__ import annotations

from typing import Any

from app.providers.embedding.bge import BGEEmbeddingProvider
from app.providers.embedding.dashscope import DashScopeEmbeddingProvider
from app.providers.embedding.fake import DeterministicFakeEmbedding


def build_embedding_provider(settings: Any):
    provider = str(settings.embedding_provider).lower()
    if provider in {"fake", "deterministic_fake"}:
        if getattr(settings, "app_env", "development").lower() in {"production", "prod"}:
            raise ValueError("FAKE_EMBEDDING_FORBIDDEN_IN_PRODUCTION")
        return DeterministicFakeEmbedding(dimension=settings.embedding_dimension)
    if provider == "dashscope":
        key = settings.embedding_api_key.get_secret_value() if hasattr(settings.embedding_api_key, "get_secret_value") else settings.embedding_api_key
        if not key:
            raise ValueError("EMBEDDING_PROVIDER_CONFIGURATION_INVALID: EMBEDDING_API_KEY")
        return DashScopeEmbeddingProvider(
            key,
            model=settings.embedding_model,
            base_url=settings.embedding_base_url,
            dimension=settings.embedding_dimension,
            batch_size=settings.embedding_batch_size,
            timeout_seconds=settings.embedding_timeout_seconds,
            connect_timeout_seconds=settings.embedding_connect_timeout_seconds,
            max_retries=settings.embedding_max_retries,
            output_type=settings.embedding_output_type,
        )
    if provider in {"huggingface", "bge", "local"}:
        return BGEEmbeddingProvider(model_name=settings.embedding_model)
    raise ValueError("EMBEDDING_PROVIDER_CONFIGURATION_INVALID")
