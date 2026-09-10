import os

import pytest

from app.providers.adapters import (
    AmapProvider,
    CommercialEnterpriseProvider,
    FirecrawlProvider,
    TavilyProvider,
)
from app.research.models import (
    EnterpriseSearchRequest,
    MapSearchRequest,
    ToolStatus,
    WebFetchRequest,
    WebSearchRequest,
)


@pytest.mark.external
@pytest.mark.asyncio
async def test_external_provider_smoke():
    required = [
        "ENTERPRISE_API_BASE_URL",
        "ENTERPRISE_API_KEY",
        "AMAP_API_KEY",
        "TAVILY_API_KEY",
        "FIRECRAWL_API_KEY",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip(
            "External smoke requires configured credentials: " + ", ".join(missing)
        )
    enterprise = await CommercialEnterpriseProvider(
        os.environ["ENTERPRISE_API_BASE_URL"], os.environ["ENTERPRISE_API_KEY"]
    ).search_companies(
        EnterpriseSearchRequest(query="制造业", region="上海松江", page_size=1)
    )
    amap = await AmapProvider(os.environ["AMAP_API_KEY"]).search_places(
        MapSearchRequest(
            keywords="企业", region="上海松江", adcode="310117", page_size=1
        )
    )
    tavily = await TavilyProvider(os.environ["TAVILY_API_KEY"]).search(
        WebSearchRequest(query="上海松江 企业 官网", max_results=1)
    )
    firecrawl = await FirecrawlProvider(os.environ["FIRECRAWL_API_KEY"]).fetch(
        WebFetchRequest(url="https://example.com")
    )
    for result in (enterprise, amap, tavily, firecrawl):
        assert result.status in {ToolStatus.SUCCESS, ToolStatus.EMPTY}, (
            result.model_dump()
        )
