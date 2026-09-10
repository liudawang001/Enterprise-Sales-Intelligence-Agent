from __future__ import annotations

from typing import Protocol

from app.research.models import (
    EnterpriseProfileRequest,
    EnterpriseSearchRequest,
    MapPlaceDetailRequest,
    MapSearchRequest,
    ProviderCapabilities,
    ToolResult,
    WebFetchRequest,
    WebSearchRequest,
)


class EnterpriseDataProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    async def search_companies(
        self, request: EnterpriseSearchRequest
    ) -> ToolResult: ...
    async def get_company_profile(
        self, request: EnterpriseProfileRequest
    ) -> ToolResult: ...


class MapProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    async def search_places(self, request: MapSearchRequest) -> ToolResult: ...
    async def get_place_detail(self, request: MapPlaceDetailRequest) -> ToolResult: ...


class WebSearchProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    async def search(self, request: WebSearchRequest) -> ToolResult: ...


class WebFetchProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    async def fetch(self, request: WebFetchRequest) -> ToolResult: ...
