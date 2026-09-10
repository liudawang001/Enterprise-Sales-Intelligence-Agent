from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from app.scoring.enums import LeadRankStatus, MissingFieldPolicy


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ScoreComponentConfig(BaseModel):
    component: str
    weight: float = Field(gt=0, le=100)
    required_fields: list[str] = Field(default_factory=list)
    missing_policy: MissingFieldPolicy = MissingFieldPolicy.ZERO
    config: dict[str, Any] = Field(default_factory=dict)


class ScoringProfile(BaseModel):
    profile_id: str = Field(default_factory=_id)
    business_code: str
    version: int = Field(ge=1)
    components: list[ScoreComponentConfig]
    min_evidence_coverage: float = Field(default=0.5, ge=0, le=1)
    hard_required_fields: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def validate_total_weight(self):
        if round(sum(item.weight for item in self.components), 6) != 100:
            raise ValueError("scoring profile component weights must total 100")
        return self

    @property
    def required_fields(self) -> list[str]:
        return sorted({field for item in self.components for field in item.required_fields})


class ScoreComponentResult(BaseModel):
    component: str
    raw_score: float = Field(ge=0, le=1)
    weighted_score: float = Field(ge=0, le=100)
    weight: float
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class LeadScore(BaseModel):
    lead_score_id: str = Field(default_factory=_id)
    task_id: str
    task_version: int = 1
    enterprise_id: str
    criteria_snapshot_id: str
    scoring_profile_id: str
    scoring_profile_version: int
    total_score: float | None = Field(default=None, ge=0, le=100)
    component_scores: list[ScoreComponentResult] = Field(default_factory=list)
    evidence_coverage: float = Field(ge=0, le=1)
    verification_status: str
    rank_status: LeadRankStatus
    created_at: datetime = Field(default_factory=_now)


class RecommendationReason(BaseModel):
    enterprise_id: str
    summary: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=_now)


class VerifiedLeadSet(BaseModel):
    lead_set_id: str = Field(default_factory=_id)
    task_id: str
    task_version: int = 1
    criteria_snapshot_id: str
    scoring_profile_id: str
    lead_ids: list[str]
    lead_count: int = 0
    created_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def derive_count(self):
        self.lead_count = len(self.lead_ids)
        return self
