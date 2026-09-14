from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

import httpx

from app.knowledge.retrieval.models import RetrievalHit
from app.observability.metrics import metrics

logger = logging.getLogger(__name__)


class RerankerProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None, request_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.request_id = request_id


@dataclass(frozen=True)
class RerankUsage:
    total_tokens: int = 0
    requests: int = 0


class DashScopeReranker:
    provider = "dashscope"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "qwen3-rerank",
        base_url: str,
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
        max_retries: int = 3,
        return_documents: bool = False,
        max_candidates: int = 12,
        max_document_chars: int = 12000,
        profile_version: str | None = None,
        client: httpx.Client | None = None,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("RERANKER_API_KEY is required")
        if not base_url or "{" in base_url or "}" in base_url:
            raise ValueError("RERANKER_BASE_URL must be a concrete DashScope URL")
        if max_candidates < 1:
            raise ValueError("RERANKER_MAX_CANDIDATES must be positive")
        if max_document_chars < 1:
            raise ValueError("RERANKER_MAX_DOCUMENT_CHARS must be positive")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.return_documents = return_documents
        self.max_candidates = max_candidates
        self.max_document_chars = max_document_chars
        self.profile_version = profile_version or f"{model}:v1"
        self.last_usage = RerankUsage()
        self._client = client
        self._async_client = async_client

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/services/rerank/text-rerank/text-rerank"

    async def rerank(self, query: str, hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
        if not hits or top_k <= 0:
            return []
        candidates = hits[: self.max_candidates]
        truncated_count = len(hits) - len(candidates)
        documents = [hit.content[: self.max_document_chars] for hit in candidates]
        payload = {
            "model": self.model,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": min(top_k, len(candidates)), "return_documents": self.return_documents},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        client = self._async_client or httpx.AsyncClient(timeout=self.timeout)
        close = self._async_client is None
        try:
            body, latency_ms = await self._arequest_with_retries(
                lambda: client.post(self.endpoint, headers=headers, json=payload)
            )
        finally:
            if close:
                await client.aclose()
        result = self._parse_response(body, candidates, top_k, latency_ms=latency_ms, truncated_count=truncated_count)
        return result

    def rerank_sync(self, query: str, hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
        if not hits or top_k <= 0:
            return []
        candidates = hits[: self.max_candidates]
        truncated_count = len(hits) - len(candidates)
        payload = {
            "model": self.model,
            "input": {"query": query, "documents": [hit.content[: self.max_document_chars] for hit in candidates]},
            "parameters": {"top_n": min(top_k, len(candidates)), "return_documents": self.return_documents},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        client = self._client or httpx.Client(timeout=self.timeout)
        close = self._client is None
        try:
            body, latency_ms = self._request_with_retries(
                lambda: client.post(self.endpoint, headers=headers, json=payload)
            )
        finally:
            if close:
                client.close()
        return self._parse_response(body, candidates, top_k, latency_ms=latency_ms, truncated_count=truncated_count)

    def rerank_sync_in_thread(self, query: str, hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
        """Compatibility helper for callers that require a sync facade in an async loop."""
        return self.rerank_sync(query, hits, top_k)

    async def _arequest_with_retries(self, request: Callable[[], Any]) -> tuple[dict[str, Any], int]:
        for attempt in range(self.max_retries + 1):
            started = perf_counter()
            try:
                response = await request()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    metrics.add("rerank_errors_total", provider=self.provider, code="RERANK_PROVIDER_TIMEOUT")
                    raise RerankerProviderError("RERANK_PROVIDER_TIMEOUT", "reranker provider unavailable") from exc
                await asyncio.sleep(self._backoff(attempt))
                continue
            latency_ms = int((perf_counter() - started) * 1000)
            if response.status_code == 429:
                metrics.add("rerank_rate_limited_total", provider=self.provider)
            if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                retry_after = self._retry_after(response)
                await asyncio.sleep(retry_after if retry_after is not None else self._backoff(attempt))
                continue
            if response.status_code >= 400:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                code = (
                    "RERANK_RATE_LIMITED" if response.status_code == 429 else
                    "RERANK_PROVIDER_TIMEOUT" if response.status_code == 408 else
                    "RERANK_AUTHENTICATION_FAILED" if response.status_code in {401, 403} else
                    "RERANK_REQUEST_INVALID" if response.status_code in {400, 422} else
                    "RERANK_PROVIDER_UNAVAILABLE"
                )
                metrics.add("rerank_errors_total", provider=self.provider, code=code)
                raise RerankerProviderError(code, f"reranker provider returned HTTP {response.status_code}", status_code=response.status_code, request_id=self._request_id(body, response))
            try:
                body = response.json()
            except ValueError as exc:
                raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker response is not valid JSON") from exc
            if not isinstance(body, dict):
                raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker response must be a JSON object")
            return body, latency_ms
        raise RerankerProviderError("RERANK_PROVIDER_TIMEOUT", "reranker provider unavailable")

    def _request_with_retries(self, request: Callable[[], Any]) -> tuple[dict[str, Any], int]:
        for attempt in range(self.max_retries + 1):
            started = perf_counter()
            try:
                response = request()
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    metrics.add("rerank_errors_total", provider=self.provider, code="RERANK_PROVIDER_TIMEOUT")
                    raise RerankerProviderError("RERANK_PROVIDER_TIMEOUT", "reranker provider unavailable") from exc
                time.sleep(self._backoff(attempt))
                continue
            latency_ms = int((perf_counter() - started) * 1000)
            if response.status_code == 429:
                metrics.add("rerank_rate_limited_total", provider=self.provider)
            if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                retry_after = self._retry_after(response)
                time.sleep(retry_after if retry_after is not None else self._backoff(attempt))
                continue
            if response.status_code >= 400:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                code = (
                    "RERANK_RATE_LIMITED" if response.status_code == 429 else
                    "RERANK_PROVIDER_TIMEOUT" if response.status_code == 408 else
                    "RERANK_AUTHENTICATION_FAILED" if response.status_code in {401, 403} else
                    "RERANK_REQUEST_INVALID" if response.status_code in {400, 422} else
                    "RERANK_PROVIDER_UNAVAILABLE"
                )
                metrics.add("rerank_errors_total", provider=self.provider, code=code)
                raise RerankerProviderError(code, f"reranker provider returned HTTP {response.status_code}", status_code=response.status_code, request_id=self._request_id(body, response))
            try:
                body = response.json()
            except ValueError as exc:
                raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker response is not valid JSON") from exc
            if not isinstance(body, dict):
                raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker response must be a JSON object")
            return body, latency_ms
        raise RerankerProviderError("RERANK_PROVIDER_TIMEOUT", "reranker provider unavailable")

    def _parse_response(
        self,
        body: dict[str, Any],
        hits: list[RetrievalHit],
        top_k: int,
        *,
        latency_ms: int,
        truncated_count: int = 0,
    ) -> list[RetrievalHit]:
        request_id = self._request_id(body, None)
        output = body.get("output") or {}
        results = output.get("results") if isinstance(output, dict) else None
        if not isinstance(results, list):
            raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker response missing results", request_id=request_id)
        mapped: list[tuple[float, int, RetrievalHit]] = []
        seen: set[int] = set()
        for item in results:
            if not isinstance(item, dict) or "index" not in item or "relevance_score" not in item:
                raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker result missing index or relevance_score", request_id=request_id)
            index = item["index"]
            try:
                score = float(item["relevance_score"])
            except (TypeError, ValueError) as exc:
                raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker relevance_score is invalid", request_id=request_id) from exc
            if not isinstance(index, int) or index < 0 or index >= len(hits) or index in seen:
                raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker result index is invalid", request_id=request_id)
            seen.add(index)
            mapped.append((score, index, hits[index]))
        if not mapped:
            raise RerankerProviderError("RERANK_PROTOCOL_ERROR", "reranker response returned no results", request_id=request_id)
        mapped.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        for score, _, hit in mapped:
            hit.rerank_score = score
        usage = body.get("usage") or {}
        tokens = int(usage.get("total_tokens", usage.get("input_tokens", 0)) or 0)
        self.last_usage = RerankUsage(self.last_usage.total_tokens + tokens, self.last_usage.requests + 1)
        metrics.add("rerank_requests_total", provider=self.provider, model=self.model, status="success")
        metrics.add("rerank_request_duration_seconds", latency_ms / 1000, provider=self.provider)
        metrics.add("rerank_tokens_total", tokens, provider=self.provider)
        logger.info("RERANK_REQUEST_COMPLETED", extra={"provider": self.provider, "model": self.model, "profile": self.profile_version, "request_id": request_id, "latency_ms": latency_ms, "token_usage": tokens, "candidate_count": len(hits), "returned_count": min(top_k, len(mapped)), "truncated_count": truncated_count})
        return [hit for _, _, hit in mapped[:top_k]]

    @staticmethod
    def _request_id(body: Any, response: httpx.Response | None) -> str | None:
        return (body.get("request_id") if isinstance(body, dict) else None) or (response.headers.get("x-request-id") if response is not None else None)

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
