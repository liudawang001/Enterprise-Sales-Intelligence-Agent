from __future__ import annotations

import asyncio
import logging
import math
import random
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class EmbeddingProviderError(RuntimeError):
    """Stable, non-secret error raised by a remote embedding provider."""

    def __init__(self, code: str, message: str, *, status_code: int | None = None, request_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.request_id = request_id


@dataclass(frozen=True)
class EmbeddingUsage:
    total_tokens: int = 0
    requests: int = 0


class DashScopeEmbeddingProvider:
    """Native DashScope qwen text embedding provider.

    The provider deliberately exposes both sync and async facades so legacy
    graph code remains usable while FastAPI paths can use the non-blocking
    methods. Inputs are never included in logs.
    """

    provider = "dashscope"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "qwen3.7-text-embedding",
        base_url: str,
        dimension: int = 1024,
        batch_size: int = 16,
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
        max_retries: int = 3,
        output_type: str = "dense",
        client: httpx.Client | None = None,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("EMBEDDING_API_KEY is required")
        if not base_url or "{" in base_url or "}" in base_url:
            raise ValueError("EMBEDDING_BASE_URL must be a concrete DashScope URL")
        if dimension <= 0:
            raise ValueError("EMBEDDING_DIMENSION must be positive")
        if not 1 <= batch_size <= 20:
            raise ValueError("EMBEDDING_BATCH_SIZE must be between 1 and 20")
        if output_type != "dense":
            raise ValueError("EMBEDDING_OUTPUT_TYPE must be dense")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.dimension = dimension
        self.batch_size = batch_size
        self.timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.output_type = output_type
        self.profile_version = f"{model}:{dimension}:v1"
        self.last_usage = EmbeddingUsage()
        self._client = client
        self._async_client = async_client

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/services/embeddings/text-embedding/text-embedding"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._request_batch(texts[start : start + self.batch_size], text_type="document"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        if not text:
            raise ValueError("query text must not be empty")
        return self._request_batch([text], text_type="query")[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(await self._arequest_batch(texts[start : start + self.batch_size], text_type="document"))
        return vectors

    async def aembed_query(self, text: str) -> list[float]:
        if not text:
            raise ValueError("query text must not be empty")
        return (await self._arequest_batch([text], text_type="query"))[0]

    def _request_batch(self, texts: list[str], *, text_type: str) -> list[list[float]]:
        payload = self._payload(texts, text_type=text_type)
        headers = self._headers()
        client = self._client or httpx.Client(timeout=self.timeout)
        close = self._client is None
        try:
            return self._request_with_retries(lambda: client.post(self.endpoint, headers=headers, json=payload), expected_count=len(texts))
        finally:
            if close:
                client.close()

    async def _arequest_batch(self, texts: list[str], *, text_type: str) -> list[list[float]]:
        payload = self._payload(texts, text_type=text_type)
        headers = self._headers()
        client = self._async_client or httpx.AsyncClient(timeout=self.timeout)
        close = self._async_client is None
        try:
            return await self._arequest_with_retries(lambda: client.post(self.endpoint, headers=headers, json=payload), expected_count=len(texts))
        finally:
            if close:
                await client.aclose()

    def _payload(self, texts: list[str], *, text_type: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": {"texts": texts},
            "parameters": {"text_type": text_type, "dimension": self.dimension, "output_type": self.output_type},
        }

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _request_with_retries(self, request, *, expected_count: int) -> list[list[float]]:
        for attempt in range(self.max_retries + 1):
            started = perf_counter()
            try:
                response = request()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise EmbeddingProviderError("EMBEDDING_PROVIDER_TIMEOUT", "embedding provider unavailable") from exc
                self._sleep(attempt)
                continue
            if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                retry_after = self._retry_after(response)
                self._sleep(attempt, retry_after)
                continue
            return self._parse_response(response, latency_ms=int((perf_counter() - started) * 1000), expected_count=expected_count)
        raise EmbeddingProviderError("EMBEDDING_PROVIDER_TIMEOUT", "embedding provider unavailable")

    async def _arequest_with_retries(self, request, *, expected_count: int) -> list[list[float]]:
        for attempt in range(self.max_retries + 1):
            started = perf_counter()
            try:
                response = await request()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise EmbeddingProviderError("EMBEDDING_PROVIDER_TIMEOUT", "embedding provider unavailable") from exc
                await asyncio.sleep(self._backoff(attempt))
                continue
            if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                retry_after = self._retry_after(response)
                await asyncio.sleep(retry_after if retry_after is not None else self._backoff(attempt))
                continue
            return self._parse_response(response, latency_ms=int((perf_counter() - started) * 1000), expected_count=expected_count)
        raise EmbeddingProviderError("EMBEDDING_PROVIDER_TIMEOUT", "embedding provider unavailable")

    def _parse_response(self, response: httpx.Response, *, latency_ms: int, expected_count: int) -> list[list[float]]:
        request_id = response.headers.get("x-request-id")
        try:
            body = response.json()
        except ValueError as exc:
            raise EmbeddingProviderError("EMBEDDING_PROTOCOL_ERROR", "embedding response is not valid JSON", request_id=request_id) from exc
        request_id = request_id or body.get("request_id") or body.get("requestId")
        if response.status_code >= 400:
            code = "EMBEDDING_RATE_LIMITED" if response.status_code == 429 else (
                "EMBEDDING_AUTHENTICATION_FAILED" if response.status_code in {401, 403} else (
                    "EMBEDDING_REQUEST_INVALID" if response.status_code in {400, 422} else "EMBEDDING_REQUEST_FAILED"
                )
            )
            raise EmbeddingProviderError(code, f"embedding provider returned HTTP {response.status_code}", status_code=response.status_code, request_id=request_id)
        output = body.get("output") or {}
        items = output.get("embeddings") or body.get("data") or []
        if not isinstance(items, list):
            raise EmbeddingProviderError("EMBEDDING_PROTOCOL_ERROR", "embedding response missing embeddings", request_id=request_id)
        indexed: list[tuple[int, list[float]]] = []
        for position, item in enumerate(items):
            raw = item.get("embedding") if isinstance(item, dict) else item
            index = item.get("text_index", item.get("index", position)) if isinstance(item, dict) else position
            if not isinstance(raw, list) or len(raw) != self.dimension:
                raise EmbeddingProviderError("EMBEDDING_DIMENSION_MISMATCH", "embedding dimension does not match configured profile", request_id=request_id)
            vector = [float(value) for value in raw]
            if not all(math.isfinite(value) for value in vector):
                raise EmbeddingProviderError("EMBEDDING_PROTOCOL_ERROR", "embedding contains non-finite values", request_id=request_id)
            indexed.append((int(index), self._normalize(vector)))
        indexed.sort(key=lambda item: item[0])
        if len(indexed) != expected_count:
            raise EmbeddingProviderError("EMBEDDING_RESULT_COUNT_MISMATCH", "embedding response count does not match input", request_id=request_id)
        if [index for index, _ in indexed] != list(range(len(indexed))):
            raise EmbeddingProviderError("EMBEDDING_PROTOCOL_ERROR", "embedding response indices are invalid", request_id=request_id)
        usage = body.get("usage") or {}
        batch_tokens = int(usage.get("total_tokens", usage.get("input_tokens", 0)) or 0)
        self.last_usage = EmbeddingUsage(total_tokens=self.last_usage.total_tokens + batch_tokens, requests=self.last_usage.requests + 1)
        logger.info("EMBEDDING_REQUEST_COMPLETED", extra={"provider": self.provider, "request_id": request_id, "model": self.model, "embedding_profile": self.profile_version, "latency_ms": latency_ms, "token_usage": self.last_usage.total_tokens})
        return [vector for _, vector in indexed]

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        try:
            return max(0.0, float(value)) if value is not None else None
        except ValueError:
            return None

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(8.0, (2**attempt) * 0.25 + random.uniform(0, 0.1))

    def _sleep(self, attempt: int, retry_after: float | None = None) -> None:
        import time

        time.sleep(retry_after if retry_after is not None else self._backoff(attempt))
