from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ResearchRunStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CandidateStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    ENRICHED = "ENRICHED"
    FILTERED_OUT = "FILTERED_OUT"
    SELECTED_FOR_RESEARCH = "SELECTED_FOR_RESEARCH"
    RESEARCHED = "RESEARCHED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ResearchSourceType(StrEnum):
    ENTERPRISE_DATABASE = "ENTERPRISE_DATABASE"
    MAP_POI = "MAP_POI"
    WEB_SEARCH = "WEB_SEARCH"
    OFFICIAL_WEBSITE = "OFFICIAL_WEBSITE"
    WEBSITE_CANDIDATE = "WEBSITE_CANDIDATE"
    PUBLIC_WEBPAGE = "PUBLIC_WEBPAGE"


class QueryPurpose(StrEnum):
    DISCOVERY = "DISCOVERY"
    PROFILE_ENRICHMENT = "PROFILE_ENRICHMENT"
    LOCATION_DISCOVERY = "LOCATION_DISCOVERY"
    WEBSITE_DISCOVERY = "WEBSITE_DISCOVERY"
    CONTACT_DISCOVERY = "CONTACT_DISCOVERY"
    BRANCH_DISCOVERY = "BRANCH_DISCOVERY"


class FilterOutcome(StrEnum):
    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    UNKNOWN = "UNKNOWN"


class ToolStatus(StrEnum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    URL_BLOCKED = "URL_BLOCKED"


class ProviderCapabilities(BaseModel):
    supported_fields: set[str] = Field(default_factory=set)
    supported_operators: dict[str, set[str]] = Field(default_factory=dict)
    supports_region: bool = False
    supports_pagination: bool = False
    supports_profile_lookup: bool = False
    supports_batch: bool = False
    cost_tier: str = "LOW"

    def supports(self, field: str, operator: str) -> bool:
        return (
            field in self.supported_fields
            and operator in self.supported_operators.get(field, set())
        )


class ProviderQuery(BaseModel):
    query_id: str = Field(default_factory=_id)
    provider_type: str
    purpose: QueryPurpose = QueryPurpose.DISCOVERY
    query_text: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    region: str | None = None
    page: int | None = 1
    page_size: int | None = 20
    fields: list[str] = Field(default_factory=list)
    priority: int = 0
    estimated_cost: float = 0


class ResearchBudget(BaseModel):
    max_tool_calls: int = 300
    max_enterprise_search_calls: int = 60
    max_enterprise_profile_calls: int = 80
    max_map_calls: int = 60
    max_web_search_calls: int = 80
    max_web_fetch_calls: int = 120
    max_web_pages: int = 120
    max_candidates: int = 300
    max_runtime_seconds: int = 600


class SearchPlan(BaseModel):
    plan_id: str = Field(default_factory=_id)
    task_id: str
    criteria_snapshot_id: str
    target_count: int
    candidate_target: int
    discovery_queries: list[ProviderQuery]
    cheap_enrichment_fields: list[str] = Field(default_factory=list)
    deep_research_fields: list[str] = Field(default_factory=list)
    post_filter_fields: list[str] = Field(default_factory=list)
    pushdown_explain: dict[str, Any] = Field(default_factory=dict)
    budget: ResearchBudget
    batch_size: int = Field(default=10, ge=1, le=20)
    max_expansion_rounds: int = Field(default=2, ge=0, le=5)
    created_at: datetime = Field(default_factory=_now)


class ResearchRun(BaseModel):
    research_run_id: str = Field(default_factory=_id)
    task_id: str
    criteria_snapshot_id: str
    search_plan_id: str | None = None
    status: ResearchRunStatus = ResearchRunStatus.CREATED
    stage: str = "CREATED"
    budget: ResearchBudget
    used_budget: dict[str, int] = Field(default_factory=dict)
    raw_candidate_set_id: str | None = None
    cheap_enriched_set_id: str | None = None
    filtered_candidate_set_id: str | None = None
    researched_candidate_set_id: str | None = None
    error_code: str | None = None
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None


class RawEnterpriseCandidate(BaseModel):
    candidate_id: str = Field(default_factory=_id)
    research_run_id: str
    source_provider: str
    source_entity_id: str | None = None
    source_name: str
    normalized_name: str
    source_url: str | None = None
    region: str | None = None
    industry: str | None = None
    company_status: str | None = None
    basic_scale: str | None = None
    address: str | None = None
    public_phone: str | None = None
    website_candidate: str | None = None
    office_count: int | None = None
    employee_count: int | None = None
    member_count: int | None = None
    branch_count: int | None = None
    locations: list[str] = Field(default_factory=list)
    cross_region_presence: bool = False
    status: CandidateStatus = CandidateStatus.DISCOVERED
    discovered_at: datetime = Field(default_factory=_now)


class CandidateSet(BaseModel):
    candidate_set_id: str = Field(default_factory=_id)
    research_run_id: str
    parent_set_id: str | None = None
    stage: str
    criteria_snapshot_id: str
    search_plan_id: str
    candidate_ids: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    created_at: datetime = Field(default_factory=_now)


class ResearchBatch(BaseModel):
    batch_id: str = Field(default_factory=_id)
    research_run_id: str
    stage: str
    batch_index: int = 0
    status: str = "COMPLETED"
    candidate_ids: list[str] = Field(default_factory=list)
    query_ids: list[str] = Field(default_factory=list)
    error_code: str | None = None
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = Field(default_factory=_now)


class SourceRecord(BaseModel):
    source_record_id: str = Field(default_factory=_id)
    research_run_id: str
    candidate_id: str
    provider: str
    source_type: ResearchSourceType
    source_id: str | None = None
    source_url: str | None = None
    payload_json: dict[str, Any] | None = None
    content_text: str | None = None
    content_hash: str | None = None
    http_status: int | None = None
    retrieved_at: datetime = Field(default_factory=_now)


class ToolError(BaseModel):
    code: str
    message: str
    http_status: int | None = None
    retry_after_ms: int | None = None


class ToolResult(BaseModel):
    status: ToolStatus
    data: Any = None
    source_refs: list[str] = Field(default_factory=list)
    provider: str
    latency_ms: int = 0
    retryable: bool = False
    error: ToolError | None = None


class ToolRun(BaseModel):
    tool_run_id: str = Field(default_factory=_id)
    research_run_id: str
    task_id: str
    query_id: str | None = None
    tool_name: str
    provider: str
    request_hash: str
    request_summary: dict[str, Any]
    status: ToolStatus
    latency_ms: int = 0
    retry_count: int = 0
    error_code: str | None = None
    result: ToolResult | None = None
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime = Field(default_factory=_now)


class WebsiteCandidate(BaseModel):
    url: HttpUrl
    domain: str
    title: str | None = None
    source_provider: str
    search_rank: int | None = None
    matching_signals: list[str] = Field(default_factory=list)
    provisional_confidence: float = Field(ge=0, le=1)


class CompanyWebFacts(BaseModel):
    company_names: list[str] = Field(default_factory=list)
    public_phones: list[str] = Field(default_factory=list)
    public_emails: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    office_locations: list[str] = Field(default_factory=list)
    branch_names: list[str] = Field(default_factory=list)
    website_domain: str | None = None


class CandidateResearchPlan(BaseModel):
    candidate_id: str
    required_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    max_calls: int = 4
    max_pages: int = 4


class EnterpriseSearchRequest(BaseModel):
    query: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    region: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class EnterpriseProfileRequest(BaseModel):
    company_id: str


class MapSearchRequest(BaseModel):
    keywords: str
    region: str | None = None
    adcode: str | None = None
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=20, ge=1, le=25)


class MapPlaceDetailRequest(BaseModel):
    place_id: str


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=10, ge=1, le=20)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    country: str | None = None
    language: str | None = None
    safe_search: bool = True

    @field_validator("include_domains", "exclude_domains")
    @classmethod
    def validate_domains(cls, values: list[str]) -> list[str]:
        for value in values:
            if "://" in value or "/" in value or not value.strip():
                raise ValueError("domain filters must contain hostnames only")
        return values


class WebFetchRequest(BaseModel):
    url: HttpUrl
    max_chars: int = Field(default=30000, ge=1000, le=100000)


class ProviderRetentionPolicy(BaseModel):
    store_raw_payload: bool = True
    max_retention_days: int | None = None
    allowed_fields: list[str] | None = None
