from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
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


class LeadTaskRecord(Base):
    __tablename__ = "lead_tasks"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(255), index=True)
    business_code: Mapped[str | None] = mapped_column(String(80))
    active_version: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24))
    is_active: Mapped[bool] = mapped_column(Boolean, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LeadTaskVersionRecord(Base):
    __tablename__ = "lead_task_versions"
    __table_args__ = (UniqueConstraint("task_id", "version"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("lead_tasks.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    parent_version: Mapped[int | None] = mapped_column(Integer)
    business_code: Mapped[str | None] = mapped_column(String(80))
    region: Mapped[str | None] = mapped_column(String(120))
    target_count: Mapped[int | None] = mapped_column(Integer)
    constraints_json: Mapped[list] = mapped_column(JSONB)
    required_fields: Mapped[list] = mapped_column(JSONB)
    export_fields: Mapped[list] = mapped_column(JSONB)
    source_message_id: Mapped[str | None] = mapped_column(String(255))
    mutation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskMutationRecord(Base):
    __tablename__ = "task_mutations"
    __table_args__ = (UniqueConstraint("task_id", "source_message_id"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("lead_tasks.id", ondelete="CASCADE"), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    target_version: Mapped[int | None] = mapped_column(Integer)
    source_message_id: Mapped[str] = mapped_column(String(255))
    patch_json: Mapped[dict] = mapped_column(JSONB)
    preview_json: Mapped[dict | None] = mapped_column(JSONB)
    task_diff_json: Mapped[dict | None] = mapped_column(JSONB)
    criteria_diff_json: Mapped[dict | None] = mapped_column(JSONB)
    scope: Mapped[str | None] = mapped_column(String(40))
    reexecution_plan_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskExecutionSnapshotRecord(Base):
    __tablename__ = "task_execution_snapshots"
    __table_args__ = (UniqueConstraint("task_id", "task_version"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("lead_tasks.id", ondelete="CASCADE"), index=True)
    task_version: Mapped[int] = mapped_column(Integer)
    criteria_snapshot_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    search_plan_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    raw_candidate_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    filtered_candidate_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    researched_candidate_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    verified_lead_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    scoring_profile_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lead_score_set_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    is_current: Mapped[bool] = mapped_column(Boolean, index=True)
    validity: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskReexecutionPlanRecord(Base):
    __tablename__ = "task_reexecution_plans"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("lead_tasks.id", ondelete="CASCADE"), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    target_version: Mapped[int] = mapped_column(Integer)
    original_scope: Mapped[str] = mapped_column(String(40))
    final_scope: Mapped[str] = mapped_column(String(40))
    start_stage: Mapped[str] = mapped_column(String(40))
    steps_json: Mapped[list] = mapped_column(JSONB)
    reused_artifact_ids: Mapped[list] = mapped_column(JSONB)
    invalidated_artifact_ids: Mapped[list] = mapped_column(JSONB)
    required_fields: Mapped[list] = mapped_column(JSONB)
    reason_codes: Mapped[list] = mapped_column(JSONB)
    reuse_decisions: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24))
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    estimated_external_calls: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
