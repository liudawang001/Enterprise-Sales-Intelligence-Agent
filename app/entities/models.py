from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from app.entities.enums import EntityRelationType, EntityType, ResolutionStatus


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class NormalizedEnterpriseName(BaseModel):
    original: str
    normalized: str
    base_name: str
    legal_suffix: str | None = None
    branch_marker: str | None = None
    office_marker: str | None = None
    location_marker: str | None = None


class ResolutionGroup(BaseModel):
    group_id: str = Field(default_factory=_id)
    candidate_ids: list[str]
    blocking_reason: str


class ResolutionDecision(BaseModel):
    left_candidate_id: str
    right_candidate_id: str
    relation: EntityRelationType
    confidence: float = Field(ge=0, le=1)
    signals: list[str] = Field(default_factory=list)
    hard_positives: list[str] = Field(default_factory=list)
    hard_negatives: list[str] = Field(default_factory=list)
    llm_used: bool = False
    rule_version: str = "entity-resolution-v1"


class AmbiguousResolutionResult(BaseModel):
    relation: EntityRelationType
    reason: str


class AmbiguousEntityResolver(Protocol):
    def resolve(self, left: dict, right: dict, signals: list[str]) -> AmbiguousResolutionResult: ...


class CanonicalEnterprise(BaseModel):
    enterprise_id: str = Field(default_factory=_id)
    canonical_name: str
    entity_type: EntityType = EntityType.LEGAL_ENTITY
    parent_enterprise_id: str | None = None
    unified_social_credit_code: str | None = None
    primary_website: str | None = None
    primary_region: str | None = None
    resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED
    resolution_confidence: float = Field(default=1, ge=0, le=1)
    source_candidate_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class EnterpriseCandidateLink(BaseModel):
    enterprise_id: str
    candidate_id: str
    resolution_run_id: str
    decision: EntityRelationType = EntityRelationType.SAME_ENTITY
    confidence: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=_now)


class EnterpriseRelation(BaseModel):
    relation_id: str = Field(default_factory=_id)
    from_enterprise_id: str
    to_enterprise_id: str
    relation_type: EntityRelationType
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class EnterpriseLocation(BaseModel):
    location_id: str = Field(default_factory=_id)
    enterprise_id: str
    location_type: EntityType
    address: str
    normalized_address: str
    lat: float | None = None
    lng: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: str = "UNVERIFIED"


class EntityResolutionRun(BaseModel):
    resolution_run_id: str = Field(default_factory=_id)
    task_id: str
    researched_candidate_set_id: str
    status: str = "RUNNING"
    rule_version: str = "entity-resolution-v1"
    candidate_count: int = 0
    enterprise_count: int = 0
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
