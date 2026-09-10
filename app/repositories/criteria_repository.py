from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.criteria.models import LeadCriteria
from app.persistence.models.rule import LeadCriteriaSnapshotRecord


class CriteriaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, criteria: LeadCriteria) -> LeadCriteria:
        existing = await self.session.scalar(select(LeadCriteriaSnapshotRecord).where(LeadCriteriaSnapshotRecord.task_id == criteria.task_id, LeadCriteriaSnapshotRecord.task_version == criteria.task_version, LeadCriteriaSnapshotRecord.criteria_hash == criteria.criteria_hash))
        if existing:
            return self._to_domain(existing)
        payload = criteria.model_dump(mode="json")
        record = LeadCriteriaSnapshotRecord(id=UUID(criteria.criteria_id), task_id=criteria.task_id, task_version=criteria.task_version, business_code=criteria.business_code, region_scope=payload["region_scope"], target_count=criteria.target_count, hard_constraints=payload["hard_constraints"], soft_constraints=payload["soft_constraints"], required_fields=payload["required_fields"], ranking_preferences=payload["ranking_preferences"], source_rule_ids=payload["source_rule_ids"], warnings=payload["warnings"], criteria_hash=criteria.criteria_hash or "", created_at=criteria.created_at)
        self.session.add(record)
        await self.session.flush()
        return criteria

    async def get(self, criteria_id: str) -> LeadCriteria | None:
        record = await self.session.get(LeadCriteriaSnapshotRecord, UUID(criteria_id))
        return self._to_domain(record) if record else None

    @staticmethod
    def _to_domain(record: LeadCriteriaSnapshotRecord) -> LeadCriteria:
        return LeadCriteria(criteria_id=str(record.id), task_id=record.task_id, task_version=record.task_version, business_code=record.business_code, region_scope=record.region_scope, target_count=record.target_count, hard_constraints=record.hard_constraints, soft_constraints=record.soft_constraints, required_fields=record.required_fields, ranking_preferences=record.ranking_preferences, source_rule_ids=record.source_rule_ids, warnings=record.warnings, criteria_hash=record.criteria_hash, created_at=record.created_at)

