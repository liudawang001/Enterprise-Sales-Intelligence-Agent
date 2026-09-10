from __future__ import annotations

import httpx

from app.providers.http import get_json, post_json
from app.research.models import (
    EnterpriseProfileRequest,
    EnterpriseSearchRequest,
    MapPlaceDetailRequest,
    MapSearchRequest,
    ProviderCapabilities,
    ToolError,
    ToolResult,
    ToolStatus,
    WebFetchRequest,
    WebSearchRequest,
)
from app.research.safety import UrlSafetyValidator

TIMEOUT = httpx.Timeout(30, connect=5, read=20, write=10)


class CommercialEnterpriseProvider:
    """Configurable adapter for an authorized JSON commercial enterprise API."""

    name = "commercial_enterprise"
    capabilities = ProviderCapabilities(
        supported_fields={
            "region",
            "industry",
            "company_status",
            "employee_count",
            "member_count",
        },
        supported_operators={
            k: {"EQ", "IN", "GTE", "GT", "LTE", "LT"}
            for k in (
                "region",
                "industry",
                "company_status",
                "employee_count",
                "member_count",
            )
        },
        supports_region=True,
        supports_pagination=True,
        supports_profile_lookup=True,
        cost_tier="HIGH",
    )

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url, self.api_key = base_url.rstrip("/"), api_key

    async def search_companies(self, request: EnterpriseSearchRequest) -> ToolResult:
        return await post_json(
            self.name,
            f"{self.base_url}/companies/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload=request.model_dump(),
            timeout=TIMEOUT,
        )

    async def get_company_profile(
        self, request: EnterpriseProfileRequest
    ) -> ToolResult:
        return await post_json(
            self.name,
            f"{self.base_url}/companies/profile",
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload=request.model_dump(),
            timeout=TIMEOUT,
        )


class AmapProvider:
    name = "amap"
    capabilities = ProviderCapabilities(
        supported_fields={"region", "address", "office_count"},
        supported_operators={"region": {"EQ", "CONTAINS"}},
        supports_region=True,
        supports_pagination=True,
    )

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search_places(self, request: MapSearchRequest) -> ToolResult:
        payload = {
            "key": self.api_key,
            "keywords": request.keywords,
            "region": request.adcode or request.region,
            "page_num": request.page,
            "page_size": min(request.page_size, 25),
            "show_fields": "business",
        }
        raw = await get_json(
            self.name,
            "https://restapi.amap.com/v5/place/text",
            params=payload,
            timeout=TIMEOUT,
        )
        if raw.status != ToolStatus.SUCCESS:
            return raw
        body = raw.data or {}
        if str(body.get("status")) != "1":
            return ToolResult(
                status=ToolStatus.FAILED,
                provider=self.name,
                error=ToolError(
                    code=str(body.get("infocode", "AMAP_ERROR")),
                    message=str(body.get("info", "Amap error")),
                ),
            )
        return raw.model_copy(update={"data": body.get("pois", [])})

    async def get_place_detail(self, request: MapPlaceDetailRequest) -> ToolResult:
        return await get_json(
            self.name,
            "https://restapi.amap.com/v5/place/detail",
            params={"key": self.api_key, "id": request.place_id},
            timeout=TIMEOUT,
        )


class TavilyProvider:
    name = "tavily"
    capabilities = ProviderCapabilities(
        supported_fields={"website", "address", "public_phone"}, supported_operators={}
    )

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search(self, request: WebSearchRequest) -> ToolResult:
        payload = {
            "api_key": self.api_key,
            "query": request.query,
            "max_results": request.max_results,
            "include_domains": request.include_domains,
            "exclude_domains": request.exclude_domains,
            "include_answer": False,
        }
        raw = await post_json(
            self.name,
            "https://api.tavily.com/search",
            headers={},
            payload=payload,
            timeout=TIMEOUT,
        )
        return (
            raw.model_copy(update={"data": (raw.data or {}).get("results", [])})
            if raw.status == ToolStatus.SUCCESS
            else raw
        )


class FirecrawlProvider:
    name = "firecrawl"
    capabilities = ProviderCapabilities(
        supported_fields={"website", "public_phone", "address", "office_count"},
        supported_operators={},
    )

    def __init__(
        self, api_key: str, validator: UrlSafetyValidator | None = None
    ) -> None:
        self.api_key, self.validator = api_key, validator or UrlSafetyValidator()

    async def fetch(self, request: WebFetchRequest) -> ToolResult:
        verdict = await self.validator.validate(str(request.url))
        if not verdict.allowed:
            return ToolResult(
                status=ToolStatus.URL_BLOCKED,
                provider=self.name,
                error=ToolError(code="URL_BLOCKED", message=verdict.reason),
            )
        raw = await post_json(
            self.name,
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload={
                "url": str(request.url),
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
            timeout=TIMEOUT,
        )
        if raw.status == ToolStatus.SUCCESS:
            data = raw.data.get("data", raw.data) if isinstance(raw.data, dict) else {}
            redirect_url = (
                data.get("metadata", {}).get("sourceURL")
                if isinstance(data.get("metadata"), dict)
                else None
            )
            if redirect_url:
                redirect_verdict = await self.validator.validate(str(redirect_url))
                if not redirect_verdict.allowed:
                    return ToolResult(
                        status=ToolStatus.URL_BLOCKED,
                        provider=self.name,
                        error=ToolError(
                            code="REDIRECT_URL_BLOCKED", message=redirect_verdict.reason
                        ),
                    )
            markdown = str(data.get("markdown", ""))[: request.max_chars]
            raw = raw.model_copy(
                update={"data": {"url": str(request.url), "markdown": markdown}}
            )
        return raw
