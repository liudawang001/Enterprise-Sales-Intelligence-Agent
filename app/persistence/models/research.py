from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class ResearchSearchPlanRecord(Base):
    __tablename__ = "research_search_plans"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    criteria_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    plan_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResearchRunRecord(Base):
    __tablename__ = "research_runs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    criteria_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    search_plan_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(24))
    stage: Mapped[str] = mapped_column(String(40))
    budget_json: Mapped[dict] = mapped_column(JSONB)
    used_budget_json: Mapped[dict] = mapped_column(JSONB)
    raw_candidate_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cheap_enriched_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    filtered_candidate_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    researched_candidate_set_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True)
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EnterpriseCandidateRecord(Base):
    __tablename__ = "enterprise_candidates"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    research_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    source_provider: Mapped[str] = mapped_column(String(60))
    source_entity_id: Mapped[str | None] = mapped_column(String(255))
    source_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    provisional_json: Mapped[dict] = mapped_column(JSONB)
    research_status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CandidateSetRecord(Base):
    __tablename__ = "candidate_sets"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    research_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    parent_set_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidate_sets.id")
    )
    stage: Mapped[str] = mapped_column(String(40))
    criteria_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    search_plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    candidate_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CandidateSetMemberRecord(Base):
    __tablename__ = "candidate_set_members"
    candidate_set_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("candidate_sets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_candidates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer)
    selection_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResearchSourceRecordModel(Base):
    __tablename__ = "research_source_records"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    research_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("enterprise_candidates.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(60))
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None] = mapped_column(Integer)


class ToolRunRecord(Base):
    __tablename__ = "tool_runs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    research_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    query_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    tool_name: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(60))
    request_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_summary: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24))
    latency_ms: Mapped[int] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResearchBatchRecord(Base):
    __tablename__ = "research_batches"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    research_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("research_runs.id", ondelete="CASCADE"),
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(40))
    batch_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    candidate_ids: Mapped[list] = mapped_column(JSONB)
    query_ids: Mapped[list] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
