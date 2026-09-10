from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.rules.models import RuleOperator


class CompiledConstraint(BaseModel):
    field: str
    operator: RuleOperator
    value: Any
    source_rule_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class RankingPreference(BaseModel):
    field: str
    operator: RuleOperator
    value: Any
    normalized_weight: float
    source_rule_ids: list[str] = Field(default_factory=list)


class LeadCriteria(BaseModel):
    criteria_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    task_version: int
    business_code: str
    region_scope: list[str]
    target_count: int
    hard_constraints: list[CompiledConstraint] = Field(default_factory=list)
    soft_constraints: list[CompiledConstraint] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    ranking_preferences: list[RankingPreference] = Field(default_factory=list)
    source_rule_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    criteria_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CriteriaDiff(BaseModel):
    added_hard: list[CompiledConstraint] = Field(default_factory=list)
    removed_hard: list[CompiledConstraint] = Field(default_factory=list)
    changed_hard: list[dict[str, Any]] = Field(default_factory=list)
    added_soft: list[RankingPreference] = Field(default_factory=list)
    removed_soft: list[RankingPreference] = Field(default_factory=list)
    changed_soft: list[dict[str, Any]] = Field(default_factory=list)
    business_changed: bool = False
    region_changed: bool = False
    target_count_changed: bool = False

