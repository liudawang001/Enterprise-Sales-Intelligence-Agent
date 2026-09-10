from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class EntityResolutionRunRecord(Base):
    __tablename__ = "entity_resolution_runs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    candidate_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("candidate_sets.id"))
    status: Mapped[str] = mapped_column(String(24))
    rule_version: Mapped[str] = mapped_column(String(80))
    candidate_count: Mapped[int] = mapped_column(Integer)
    enterprise_count: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CanonicalEnterpriseRecord(Base):
    __tablename__ = "canonical_enterprises"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    parent_enterprise_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id"))
    unified_social_credit_code: Mapped[str | None] = mapped_column(String(32), index=True)
    primary_region: Mapped[str | None] = mapped_column(String(100))
    primary_website: Mapped[str | None] = mapped_column(Text)
    resolution_status: Mapped[str] = mapped_column(String(24))
    resolution_confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EnterpriseCandidateLinkRecord(Base):
    __tablename__ = "enterprise_candidate_links"
    enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id", ondelete="CASCADE"), primary_key=True)
    candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("enterprise_candidates.id", ondelete="CASCADE"), primary_key=True)
    resolution_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entity_resolution_runs.id"), index=True)
    decision: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EntityResolutionDecisionRecord(Base):
    __tablename__ = "entity_resolution_decisions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    resolution_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entity_resolution_runs.id", ondelete="CASCADE"), index=True)
    left_candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("enterprise_candidates.id"))
    right_candidate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("enterprise_candidates.id"))
    relation: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    audit_json: Mapped[dict] = mapped_column(JSONB)


class EnterpriseRelationRecord(Base):
    __tablename__ = "enterprise_relations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    from_enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id", ondelete="CASCADE"), index=True)
    to_enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    evidence_ids: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EnterpriseLocationRecord(Base):
    __tablename__ = "enterprise_locations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id", ondelete="CASCADE"), index=True)
    location_type: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(Text)
    normalized_address: Mapped[str] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    evidence_ids: Mapped[list] = mapped_column(JSONB)
    verification_status: Mapped[str] = mapped_column(String(24))


class VerificationRunRecord(Base):
    __tablename__ = "verification_runs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    candidate_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("candidate_sets.id"))
    resolution_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entity_resolution_runs.id"))
    status: Mapped[str] = mapped_column(String(24))
    budget_json: Mapped[dict] = mapped_column(JSONB)
    used_budget_json: Mapped[dict] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EnterpriseEvidenceRecord(Base):
    __tablename__ = "enterprise_evidence"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(100), index=True)
    value_json: Mapped[object] = mapped_column(JSONB)
    normalized_value_json: Mapped[object | None] = mapped_column(JSONB)
    provider: Mapped[str] = mapped_column(String(60))
    source_type: Mapped[str] = mapped_column(String(40))
    source_record_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("research_source_records.id"), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(Float)
    extraction_method: Mapped[str] = mapped_column(String(32))
    raw_reference: Mapped[str | None] = mapped_column(Text)
    stale: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResolvedFieldRecord(Base):
    __tablename__ = "resolved_fields"
    __table_args__ = (UniqueConstraint("verification_run_id", "enterprise_id", "field_name"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    verification_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("verification_runs.id", ondelete="CASCADE"), index=True)
    enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    primary_value_json: Mapped[object | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24))
    confidence: Mapped[float] = mapped_column(Float)
    supporting_evidence_ids: Mapped[list] = mapped_column(JSONB)
    conflicting_evidence_ids: Mapped[list] = mapped_column(JSONB)
    alternatives: Mapped[list] = mapped_column(JSONB)
    selection_reason: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VerifiedEnterpriseProfileRecord(Base):
    __tablename__ = "verified_enterprise_profiles"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    verification_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("verification_runs.id", ondelete="CASCADE"), index=True)
    enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id", ondelete="CASCADE"), index=True)
    profile_json: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24))
    evidence_coverage: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScoringProfileRecord(Base):
    __tablename__ = "scoring_profiles"
    __table_args__ = (UniqueConstraint("business_code", "version"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    business_code: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int] = mapped_column(Integer)
    profile_json: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LeadScoreRecord(Base):
    __tablename__ = "lead_scores"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    task_version: Mapped[int | None] = mapped_column(Integer)
    enterprise_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("canonical_enterprises.id"), index=True)
    criteria_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("lead_criteria_snapshots.id"))
    scoring_profile_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scoring_profiles.id"))
    scoring_profile_version: Mapped[int] = mapped_column(Integer)
    total_score: Mapped[float | None] = mapped_column(Float)
    rank_status: Mapped[str] = mapped_column(String(24))
    verification_status: Mapped[str] = mapped_column(String(24))
    evidence_coverage: Mapped[float] = mapped_column(Float)
    component_scores: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecommendationReasonRecord(Base):
    __tablename__ = "recommendation_reasons"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    lead_score_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("lead_scores.id", ondelete="CASCADE"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    reason_codes: Mapped[list] = mapped_column(JSONB)
    evidence_ids: Mapped[list] = mapped_column(JSONB)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VerifiedLeadSetRecord(Base):
    __tablename__ = "verified_lead_sets"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    task_version: Mapped[int | None] = mapped_column(Integer)
    criteria_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("lead_criteria_snapshots.id"))
    scoring_profile_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scoring_profiles.id"))
    lead_ids: Mapped[list] = mapped_column(JSONB)
    lead_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
