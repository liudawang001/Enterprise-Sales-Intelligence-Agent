from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class ArtifactValidity(StrEnum):
    CURRENT = "CURRENT"
    REUSABLE = "REUSABLE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class TaskExecutionSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    task_version: int
    criteria_snapshot_id: str | None = None
    search_plan_id: str | None = None
    raw_candidate_set_id: str | None = None
    filtered_candidate_set_id: str | None = None
    researched_candidate_set_id: str | None = None
    verified_lead_set_id: str | None = None
    scoring_profile_id: str | None = None
    lead_score_set_id: str | None = None
    is_current: bool = False
    validity: ArtifactValidity = ArtifactValidity.REUSABLE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
