from dataclasses import dataclass

from app.config import Settings
from app.providers.adapters import (
    AmapProvider,
    CommercialEnterpriseProvider,
    FirecrawlProvider,
    TavilyProvider,
)
from app.providers.fakes import (
    FakeEnterpriseProvider,
    FakeMapProvider,
    FakeWebFetchProvider,
    FakeWebSearchProvider,
)
from app.providers.research import (
    EnterpriseDataProvider,
    MapProvider,
    WebFetchProvider,
    WebSearchProvider,
)


@dataclass
class ResearchProviders:
    enterprise: EnterpriseDataProvider
    map: MapProvider
    web_search: WebSearchProvider
    web_fetch: WebFetchProvider


class ProviderFactory:
    @staticmethod
    def build(settings: Settings) -> ResearchProviders:
        enterprise = (
            CommercialEnterpriseProvider(
                settings.enterprise_api_base_url, settings.enterprise_api_key
            )
            if settings.enterprise_provider == "commercial"
            and settings.enterprise_api_base_url
            and settings.enterprise_api_key
            else FakeEnterpriseProvider()
        )
        map_provider = (
            AmapProvider(settings.amap_api_key)
            if settings.map_provider == "amap" and settings.amap_api_key
            else FakeMapProvider()
        )
        search = (
            TavilyProvider(settings.tavily_api_key)
            if settings.web_search_provider == "tavily" and settings.tavily_api_key
            else FakeWebSearchProvider()
        )
        fetch = (
            FirecrawlProvider(settings.firecrawl_api_key)
            if settings.web_fetch_provider == "firecrawl" and settings.firecrawl_api_key
            else FakeWebFetchProvider()
        )
        return ResearchProviders(
            enterprise=enterprise, map=map_provider, web_search=search, web_fetch=fetch
        )
