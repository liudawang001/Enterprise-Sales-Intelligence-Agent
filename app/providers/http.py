from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from app.research.models import ToolError, ToolResult, ToolStatus


def map_http_error(
    provider: str,
    status: int,
    message: str = "provider request failed",
    retry_after_ms: int | None = None,
) -> ToolResult:
    retryable = status in {429, 502, 503}
    return ToolResult(
        status=ToolStatus.FAILED,
        provider=provider,
        retryable=retryable,
        error=ToolError(
            code=f"HTTP_{status}",
            message=message,
            http_status=status,
            retry_after_ms=retry_after_ms,
        ),
    )


async def post_json(
    provider: str,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: httpx.Timeout,
) -> ToolResult:
    started = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
        latency = int((perf_counter() - started) * 1000)
        if response.status_code >= 400:
            retry_after = response.headers.get("retry-after")
            retry_after_ms = (
                int(float(retry_after) * 1000)
                if retry_after and retry_after.replace(".", "", 1).isdigit()
                else None
            )
            result = map_http_error(
                provider, response.status_code, retry_after_ms=retry_after_ms
            )
            return result.model_copy(update={"latency_ms": latency})
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=response.json(),
            provider=provider,
            latency_ms=latency,
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        return ToolResult(
            status=ToolStatus.FAILED,
            provider=provider,
            latency_ms=int((perf_counter() - started) * 1000),
            retryable=True,
            error=ToolError(code="TRANSIENT_NETWORK", message=str(exc)),
        )
    except (ValueError, httpx.HTTPError) as exc:
        return ToolResult(
            status=ToolStatus.FAILED,
            provider=provider,
            latency_ms=int((perf_counter() - started) * 1000),
            error=ToolError(code="MALFORMED_RESPONSE", message=str(exc)),
        )


async def get_json(
    provider: str, url: str, *, params: dict[str, Any], timeout: httpx.Timeout
) -> ToolResult:
    started = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.get(url, params=params)
        latency = int((perf_counter() - started) * 1000)
        if response.status_code >= 400:
            retry_after = response.headers.get("retry-after")
            retry_after_ms = (
                int(float(retry_after) * 1000)
                if retry_after and retry_after.replace(".", "", 1).isdigit()
                else None
            )
            return map_http_error(
                provider, response.status_code, retry_after_ms=retry_after_ms
            ).model_copy(update={"latency_ms": latency})
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=response.json(),
            provider=provider,
            latency_ms=latency,
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        return ToolResult(
            status=ToolStatus.FAILED,
            provider=provider,
            latency_ms=int((perf_counter() - started) * 1000),
            retryable=True,
            error=ToolError(code="TRANSIENT_NETWORK", message=str(exc)),
        )
    except (ValueError, httpx.HTTPError) as exc:
        return ToolResult(
            status=ToolStatus.FAILED,
            provider=provider,
            latency_ms=int((perf_counter() - started) * 1000),
            error=ToolError(code="MALFORMED_RESPONSE", message=str(exc)),
        )
