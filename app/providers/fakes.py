from __future__ import annotations

from app.research.models import (
    EnterpriseProfileRequest,
    EnterpriseSearchRequest,
    MapPlaceDetailRequest,
    MapSearchRequest,
    ProviderCapabilities,
    ToolResult,
    ToolStatus,
    WebFetchRequest,
    WebSearchRequest,
)

FIXTURES = [
    {
        "id": "ent-001",
        "name": "上海华东智造有限公司",
        "region": "上海松江",
        "industry": "制造业",
        "company_status": "ACTIVE",
        "employee_count": 260,
        "member_count": 120,
        "office_count": 3,
        "address": "上海市松江区新桥镇",
        "public_phone": "021-55550001",
        "website": "https://huadong.example.com",
        "locations": ["上海松江", "上海闵行"],
        "company_scale": "LARGE",
        "cross_region_presence": True,
    },
    {
        "id": "ent-002",
        "name": "松江现代物流有限公司",
        "region": "上海松江",
        "industry": "物流",
        "company_status": "ACTIVE",
        "employee_count": 90,
        "member_count": 45,
        "office_count": 2,
        "address": "上海市松江区九亭镇",
        "public_phone": "021-55550002",
        "website": "https://songjiang-logistics.example.com",
        "locations": ["上海松江"],
        "company_scale": "MEDIUM",
    },
    {
        "id": "ent-003",
        "name": "上海云创科技有限公司",
        "region": "上海松江",
        "industry": "科技",
        "company_status": "ACTIVE",
        "employee_count": 70,
        "member_count": 30,
        "office_count": 2,
        "address": "上海市松江区广富林路",
        "website": "https://yunchuang.example.com",
        "locations": ["上海松江"],
        "company_scale": "MEDIUM",
    },
    {
        "id": "ent-004",
        "name": "东华工业设备有限公司",
        "region": "上海松江",
        "industry": "制造业",
        "company_status": "ACTIVE",
        "employee_count": 55,
        "member_count": 20,
        "office_count": 1,
        "address": "上海市松江区车墩镇",
        "locations": ["上海松江"],
        "company_scale": "MEDIUM",
    },
    {
        "id": "ent-005",
        "name": "上海新联供应链有限公司",
        "region": "上海松江",
        "industry": "物流",
        "company_status": "ACTIVE",
        "employee_count": 35,
        "member_count": 8,
        "office_count": 2,
        "address": "上海市松江区洞泾镇",
        "locations": ["上海松江"],
        "company_scale": "SMALL",
    },
]


class FakeEnterpriseProvider:
    name = "fake_enterprise"
    capabilities = ProviderCapabilities(
        supported_fields={
            "region",
            "industry",
            "company_status",
            "employee_count",
            "member_count",
            "company_scale",
        },
        supported_operators={
            k: {"EQ", "IN", "GTE", "GT", "LTE", "LT"}
            for k in (
                "region",
                "industry",
                "company_status",
                "employee_count",
                "member_count",
                "company_scale",
            )
        },
        supports_region=True,
        supports_pagination=True,
        supports_profile_lookup=True,
    )

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or FIXTURES
        self.call_count = 0

    async def search_companies(self, request: EnterpriseSearchRequest) -> ToolResult:
        self.call_count += 1
        rows = [
            dict(r)
            for r in self.rows
            if not request.region or request.region in str(r.get("region", ""))
        ]
        start = (request.page - 1) * request.page_size
        return ToolResult(
            status=ToolStatus.SUCCESS if rows else ToolStatus.EMPTY,
            data=rows[start : start + request.page_size],
            provider=self.name,
        )

    async def get_company_profile(
        self, request: EnterpriseProfileRequest
    ) -> ToolResult:
        self.call_count += 1
        row = next((dict(r) for r in self.rows if r["id"] == request.company_id), None)
        return ToolResult(
            status=ToolStatus.SUCCESS if row else ToolStatus.EMPTY,
            data=row,
            provider=self.name,
        )


class FakeMapProvider:
    name = "fake_map"
    capabilities = ProviderCapabilities(
        supported_fields={"region", "office_count", "address"},
        supported_operators={"region": {"EQ", "CONTAINS"}},
        supports_region=True,
        supports_pagination=True,
    )

    async def search_places(self, request: MapSearchRequest) -> ToolResult:
        if request.region and request.keywords.startswith(request.region):
            return ToolResult(status=ToolStatus.EMPTY, data=[], provider=self.name)
        data = [
            {
                "id": f"poi-{request.page}",
                "name": request.keywords,
                "address": f"{request.region or '上海'}公开办公地址",
                "region": request.region,
                "location": "121.2,31.0",
            }
        ]
        return ToolResult(status=ToolStatus.SUCCESS, data=data, provider=self.name)

    async def get_place_detail(self, request: MapPlaceDetailRequest) -> ToolResult:
        return ToolResult(
            status=ToolStatus.SUCCESS, data={"id": request.place_id}, provider=self.name
        )


class FakeWebSearchProvider:
    name = "fake_web_search"
    capabilities = ProviderCapabilities(
        supported_fields={"website", "public_phone"}, supported_operators={}
    )

    def __init__(self) -> None:
        self.call_count = 0

    async def search(self, request: WebSearchRequest) -> ToolResult:
        self.call_count += 1
        if '"' not in request.query and ("官网" in request.query or "企业名录" in request.query):
            return ToolResult(status=ToolStatus.EMPTY, data=[], provider=self.name)
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=[
                {
                    "title": request.query,
                    "url": "https://example.com",
                    "content": "公开企业页面",
                    "score": 0.9,
                }
            ],
            provider=self.name,
        )


class FakeWebFetchProvider:
    name = "fake_web_fetch"
    capabilities = ProviderCapabilities(
        supported_fields={"website", "public_phone", "address", "office_count"},
        supported_operators={},
    )

    def __init__(self) -> None:
        self.call_count = 0

    async def fetch(self, request: WebFetchRequest) -> ToolResult:
        self.call_count += 1
        return ToolResult(
            status=ToolStatus.SUCCESS,
            data={
                "url": str(request.url),
                "markdown": "公司总机：021-55550000\n联系人：13800138000\n联系我们",
            },
            source_refs=[str(request.url)],
            provider=self.name,
        )
