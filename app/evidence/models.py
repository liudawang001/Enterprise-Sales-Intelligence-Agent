from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.evidence.enums import (
    EnterpriseVerificationStatus,
    EvidenceSourceType,
    FieldVerificationStatus,
)


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=_id)
    enterprise_id: str
    field_name: str
    value: Any
    normalized_value: Any | None = None
    provider: str
    source_type: EvidenceSourceType
    source_record_id: str
    source_url: str | None = None
    retrieved_at: datetime
    confidence: float = Field(default=0, ge=0, le=1)
    extraction_method: str
    raw_reference: str | None = None
    stale: bool = False
    created_at: datetime = Field(default_factory=_now)


class FieldVerificationPolicy(BaseModel):
    field_name: str
    source_priorities: list[EvidenceSourceType]
    min_sources_for_verified: int = Field(default=2, ge=1)
    min_confidence: float = Field(default=0.7, ge=0, le=1)
    conflict_tolerance: str = "NONE"
    max_age_days: int | None = None


class ResolvedField(BaseModel):
    resolved_field_id: str = Field(default_factory=_id)
    enterprise_id: str
    field_name: str
    primary_value: Any | None = None
    status: FieldVerificationStatus
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    conflicting_evidence_ids: list[str] = Field(default_factory=list)
    alternatives: list[Any] = Field(default_factory=list)
    selection_reason: str | None = None
    resolved_at: datetime = Field(default_factory=_now)


class VerifiedEnterpriseProfile(BaseModel):
    profile_id: str = Field(default_factory=_id)
    verification_run_id: str
    enterprise_id: str
    fields: dict[str, ResolvedField] = Field(default_factory=dict)
    addresses: list[ResolvedField] = Field(default_factory=list)
    status: EnterpriseVerificationStatus
    evidence_coverage: float = Field(ge=0, le=1)
    required_fields: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=_now)

    def field(self, name: str) -> ResolvedField | None:
        return self.fields.get(name)


class VerificationBudget(BaseModel):
    max_extra_tool_calls: int = Field(default=100, ge=0)
    max_calls_per_entity: int = Field(default=3, ge=0)
    max_web_pages: int = Field(default=100, ge=0)
    max_candidates: int = Field(default=100, ge=0)
    max_runtime_seconds: int = Field(default=300, ge=1)
    max_rounds: int = Field(default=1, ge=0, le=3)


class VerificationRun(BaseModel):
    verification_run_id: str = Field(default_factory=_id)
    task_id: str
    researched_candidate_set_id: str
    resolution_run_id: str | None = None
    status: str = "RUNNING"
    budget: VerificationBudget
    used_budget: dict[str, int] = Field(default_factory=dict)
    profile_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
