from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class DeliverySnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=_id)
    task_id: str
    task_version: int
    criteria_snapshot_id: str | None = None
    verified_lead_set_id: str
    lead_score_set_id: str
    scoring_profile_id: str | None = None
    result_count: int
    execution_snapshot_id: str | None = None
    created_at: datetime = Field(default_factory=_now)


class EvidenceDTO(BaseModel):
    evidence_id: str
    enterprise_id: str
    field_name: str
    value: Any
    normalized_value: Any | None = None
    verification_role: str
    provider: str
    source_type: str
    source_record_id: str
    source_url: str | None = None
    retrieved_at: datetime
    confidence: float


class DeliveryLeadRow(BaseModel):
    rank: int
    enterprise_id: str
    enterprise_name: str
    parent_enterprise: str | None = None
    industry: str | None = None
    company_scale: str | None = None
    region: str | None = None
    office_count: int | None = None
    office_address: str | None = None
    public_phone: str | None = None
    website: str | None = None
    recommended_business: str
    lead_score: float | None = None
    score_status: str
    verification_status: str
    evidence_confidence: float | None = None
    recommendation_reason: str | None = None
    primary_source: str | None = None
    primary_source_url: str | None = None
    verified_at: datetime | None = None
    field_statuses: dict[str, str] = Field(default_factory=dict)


class ScoreExplainDTO(BaseModel):
    enterprise_id: str
    lead_score_id: str
    total_score: float | None = None
    rank_status: str
    verification_status: str
    evidence_coverage: float
    scoring_profile_id: str
    scoring_profile_version: int
    components: list[dict[str, Any]] = Field(default_factory=list)
    recommendation_reason: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class LeadDetailDTO(BaseModel):
    snapshot_id: str
    task_id: str
    task_version: int
    score_set_id: str
    lead: DeliveryLeadRow
    enterprise_profile: dict[str, Any]
    relations: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    resolved_fields: list[dict[str, Any]] = Field(default_factory=list)
    score: ScoreExplainDTO
    evidence: list[EvidenceDTO] = Field(default_factory=list)


class TaskSummaryDTO(BaseModel):
    task_id: str
    session_id: str
    business: str | None = None
    region: str | None = None
    target_count: int | None = None
    status: str
    stage: str
    active: bool
    current_version: int
    viewed_version: int
    historical: bool
    result_count: int
    updated_at: datetime
    criteria_snapshot_id: str | None = None
    verified_lead_set_id: str | None = None
    lead_score_set_id: str | None = None
    current_mutation_scope: str | None = None
    hard_constraints: list[dict[str, Any]] = Field(default_factory=list)
    soft_preferences: list[dict[str, Any]] = Field(default_factory=list)


class TaskVersionDTO(BaseModel):
    task_id: str
    version: int
    parent_version: int | None = None
    business: str | None = None
    region: str | None = None
    target_count: int | None = None
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    export_fields: list[str] = Field(default_factory=list)
    read_only: bool
    created_at: datetime


class DeliveryBundle(BaseModel):
    snapshot: DeliverySnapshot
    task: TaskSummaryDTO
    leads: list[DeliveryLeadRow]
    details: dict[str, LeadDetailDTO]


class LeadPageDTO(BaseModel):
    snapshot_id: str
    task_id: str
    task_version: int
    score_set_id: str
    page: int
    page_size: int
    total: int
    total_pages: int
    sort_by: str
    sort_order: str
    view_sort: bool
    items: list[DeliveryLeadRow]
    quality_summary: dict[str, float | int]
