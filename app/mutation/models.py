from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.agent.enums import MutationScope
from app.criteria.models import CriteriaDiff
from app.domain.task import TaskPatch


class TaskDiff(BaseModel):
    business_changed: bool = False
    region_changed: bool = False
    target_count_changed: bool = False
    required_fields_changed: bool = False
    export_fields_changed: bool = False
    constraint_fields_changed: list[str] = Field(default_factory=list)
    hard_constraints_changed: bool = False
    soft_constraints_changed: bool = False


class MutationPreview(BaseModel):
    task_id: str
    base_version: int
    next_version: int
    before: dict[str, Any]
    after: dict[str, Any]
    patch: TaskPatch


class TaskMutation(BaseModel):
    mutation_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    source_message_id: str
    base_version: int
    target_version: int | None = None
    patch: TaskPatch
    preview: MutationPreview | None = None
    task_diff: TaskDiff | None = None
    criteria_diff: CriteriaDiff | None = None
    scope: MutationScope | None = None
    reexecution_plan_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReuseDecision(StrEnum):
    REUSE = "REUSE"
    REBUILD = "REBUILD"
    EXTEND = "EXTEND"
    REVERIFY = "REVERIFY"


class ReexecutionPlanStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class ArtifactReuseContext(BaseModel):
    task_id: str
    task_version: int
    criteria_snapshot_id: str | None = None
    search_plan_id: str | None = None
    raw_candidate_set_id: str | None = None
    raw_candidate_count: int = 0
    filtered_candidate_set_id: str | None = None
    filtered_candidate_count: int = 0
    researched_candidate_set_id: str | None = None
    researched_candidate_count: int = 0
    verified_lead_set_id: str | None = None
    verified_lead_count: int = 0
    lead_score_set_id: str | None = None
    scored_lead_count: int = 0
    scoring_profile_id: str | None = None
    available_candidate_fields: set[str] = Field(default_factory=set)
    available_verified_fields: set[str] = Field(default_factory=set)
    discovery_pushdown_fields: set[str] = Field(default_factory=set)
    post_filter_fields: set[str] = Field(default_factory=set)
    enrichment_fields: set[str] = Field(default_factory=set)
    field_dependencies: dict[str, list[str]] = Field(default_factory=dict)


class ReexecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    base_version: int
    next_version: int
    original_scope: MutationScope
    final_scope: MutationScope
    start_stage: str
    steps: list[str]
    reused_artifact_ids: list[str] = Field(default_factory=list)
    invalidated_artifact_ids: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    reuse_decisions: dict[str, ReuseDecision] = Field(default_factory=dict)
    estimated_external_calls: int | None = None
    status: ReexecutionPlanStatus = ReexecutionPlanStatus.PLANNED
    escalation_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def scope(self) -> MutationScope:
        return self.final_scope
