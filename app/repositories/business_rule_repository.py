from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models.rule import BusinessRuleEvidenceRecord, BusinessRuleRecord
from app.rules.models import BusinessRule


class BusinessRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, rule: BusinessRule) -> BusinessRule:
        existing = await self.session.scalar(select(BusinessRuleRecord).where(BusinessRuleRecord.source_key == (rule.source_key or rule.rule_id)))
        if existing:
            return self._to_domain(existing)
        record = BusinessRuleRecord(id=UUID(rule.rule_id), business_code=rule.business_code, field=rule.field, operator=rule.operator.value, value=rule.value, value_type=rule.value_type, source_type=rule.source_type.value, constraint_type=rule.constraint_type.value, modality=rule.modality.value if rule.modality else None, weight=rule.weight, confidence=rule.confidence, rationale=rule.rationale, region=rule.region, effective_from=rule.effective_from, effective_to=rule.effective_to, status=rule.status.value, source_key=rule.source_key or rule.rule_id, created_at=rule.created_at)
        self.session.add(record)
        await self.session.flush()
        for provenance in rule.provenance:
            if provenance.document_id and provenance.chunk_id:
                self.session.add(BusinessRuleEvidenceRecord(id=uuid4(), rule_id=record.id, document_id=UUID(provenance.document_id), chunk_id=UUID(provenance.chunk_id), page_start=provenance.page_start, page_end=provenance.page_end, excerpt=provenance.evidence_text or ""))
        await self.session.flush()
        return rule

    async def get(self, rule_id: str) -> BusinessRule | None:
        record = await self.session.get(BusinessRuleRecord, UUID(rule_id))
        return self._to_domain(record) if record else None

    @staticmethod
    def _to_domain(record: BusinessRuleRecord) -> BusinessRule:
        return BusinessRule(rule_id=str(record.id), business_code=record.business_code, field=record.field, operator=record.operator, value=record.value, value_type=record.value_type, source_type=record.source_type, constraint_type=record.constraint_type, modality=record.modality, weight=float(record.weight) if record.weight is not None else None, confidence=float(record.confidence), rationale=record.rationale, region=record.region, effective_from=record.effective_from, effective_to=record.effective_to, status=record.status, source_key=record.source_key, created_at=record.created_at)
