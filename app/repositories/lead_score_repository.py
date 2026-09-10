from __future__ import annotations

from copy import deepcopy
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models.verification import (
    LeadScoreRecord,
    RecommendationReasonRecord,
    ScoringProfileRecord,
    VerifiedLeadSetRecord,
)
from app.scoring.models import (
    LeadScore,
    RecommendationReason,
    ScoringProfile,
    VerifiedLeadSet,
)


class InMemoryLeadScoreRepository:
    def __init__(self) -> None:
        self.profiles: dict[str, ScoringProfile] = {}
        self.scores: dict[str, LeadScore] = {}
        self.reasons: dict[str, RecommendationReason] = {}
        self.lead_sets: dict[str, VerifiedLeadSet] = {}

    def save_profile(self, value: ScoringProfile) -> ScoringProfile:
        existing = next((item for item in self.profiles.values() if item.business_code == value.business_code and item.version == value.version), None)
        if existing:
            excluded = {"profile_id", "created_at"}
            if existing.model_dump(mode="json", exclude=excluded) != value.model_dump(mode="json", exclude=excluded):
                raise ValueError("SCORING_PROFILE_VERSION_IMMUTABLE")
            return deepcopy(existing)
        self.profiles[value.profile_id] = deepcopy(value)
        return deepcopy(value)

    def active_profile(self, business_code: str) -> ScoringProfile | None:
        values = [item for item in self.profiles.values() if item.business_code == business_code and item.active]
        return deepcopy(max(values, key=lambda item: item.version)) if values else None

    def save_score(self, value: LeadScore) -> LeadScore:
        self.scores[value.lead_score_id] = deepcopy(value)
        return deepcopy(value)

    def save_reason(self, value: RecommendationReason) -> RecommendationReason:
        self.reasons[value.enterprise_id] = deepcopy(value)
        return deepcopy(value)

    def save_lead_set(self, value: VerifiedLeadSet) -> VerifiedLeadSet:
        self.lead_sets[value.lead_set_id] = deepcopy(value)
        return deepcopy(value)

    def list_for_task(self, task_id: str) -> list[LeadScore]:
        return [deepcopy(item) for item in self.scores.values() if item.task_id == task_id]

    def get_for_enterprise(self, enterprise_id: str) -> LeadScore | None:
        values = [item for item in self.scores.values() if item.enterprise_id == enterprise_id]
        return deepcopy(values[-1]) if values else None


class LeadScoreRepository:
    """PostgreSQL adapter preserving profile versions and score provenance."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_profile(self, value: ScoringProfile) -> ScoringProfile:
        existing = await self.session.scalar(select(ScoringProfileRecord).where(ScoringProfileRecord.business_code == value.business_code, ScoringProfileRecord.version == value.version))
        if existing:
            stored = ScoringProfile.model_validate(existing.profile_json)
            excluded = {"profile_id", "created_at"}
            if stored.model_dump(mode="json", exclude=excluded) != value.model_dump(mode="json", exclude=excluded):
                raise ValueError("SCORING_PROFILE_VERSION_IMMUTABLE")
            return stored
        self.session.add(ScoringProfileRecord(id=UUID(value.profile_id), business_code=value.business_code, version=value.version, profile_json=value.model_dump(mode="json"), active=value.active, created_at=value.created_at))
        await self.session.flush()
        return value

    async def save_score(self, value: LeadScore) -> LeadScore:
        if not await self.session.get(LeadScoreRecord, UUID(value.lead_score_id)):
            self.session.add(LeadScoreRecord(id=UUID(value.lead_score_id), task_id=value.task_id, enterprise_id=UUID(value.enterprise_id), criteria_snapshot_id=UUID(value.criteria_snapshot_id), scoring_profile_id=UUID(value.scoring_profile_id), scoring_profile_version=value.scoring_profile_version, total_score=value.total_score, rank_status=value.rank_status.value, verification_status=value.verification_status, evidence_coverage=value.evidence_coverage, component_scores=[item.model_dump(mode="json") for item in value.component_scores], created_at=value.created_at))
            await self.session.flush()
        return value

    async def save_reason(self, value: RecommendationReason, *, lead_score_id: str) -> RecommendationReason:
        existing = await self.session.scalar(select(RecommendationReasonRecord).where(RecommendationReasonRecord.lead_score_id == UUID(lead_score_id)))
        if not existing:
            self.session.add(RecommendationReasonRecord(id=uuid4(), lead_score_id=UUID(lead_score_id), summary=value.summary, reason_codes=value.reason_codes, evidence_ids=value.evidence_ids, generated_at=value.generated_at))
            await self.session.flush()
        return value

    async def save_lead_set(self, value: VerifiedLeadSet) -> VerifiedLeadSet:
        if not await self.session.get(VerifiedLeadSetRecord, UUID(value.lead_set_id)):
            self.session.add(VerifiedLeadSetRecord(id=UUID(value.lead_set_id), task_id=value.task_id, criteria_snapshot_id=UUID(value.criteria_snapshot_id), scoring_profile_id=UUID(value.scoring_profile_id), lead_ids=value.lead_ids, lead_count=value.lead_count, created_at=value.created_at))
            await self.session.flush()
        return value
