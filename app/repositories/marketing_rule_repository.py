from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models.rule import MarketingRuleRecord
from app.rules.models import BusinessRule, ConstraintType, RuleSourceType, RuleStatus


class MarketingRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, rule: BusinessRule) -> BusinessRule:
        record = MarketingRuleRecord(id=UUID(rule.rule_id), business_code=rule.business_code, field=rule.field, operator=rule.operator.value, value=rule.value, value_type=rule.value_type, constraint_type=rule.constraint_type.value, weight=rule.weight, region=rule.region, effective_from=rule.effective_from, effective_to=rule.effective_to, rationale=rule.rationale, status=rule.status.value, source_key=rule.source_key or rule.rule_id, created_at=rule.created_at)
        self.session.add(record)
        await self.session.flush()
        return rule

    async def list_active(self, business_code: str, region: str | None = None, at: date | None = None) -> list[BusinessRule]:
        at = at or date.today()
        query = select(MarketingRuleRecord).where(MarketingRuleRecord.business_code == business_code, MarketingRuleRecord.status == RuleStatus.ACTIVE.value, or_(MarketingRuleRecord.effective_from.is_(None), MarketingRuleRecord.effective_from <= at), or_(MarketingRuleRecord.effective_to.is_(None), MarketingRuleRecord.effective_to >= at))
        if region:
            query = query.where(or_(MarketingRuleRecord.region.is_(None), MarketingRuleRecord.region == region))
        records = (await self.session.scalars(query)).all()
        return [BusinessRule(rule_id=str(r.id), business_code=r.business_code, field=r.field, operator=r.operator, value=r.value, value_type=r.value_type, source_type=RuleSourceType.MARKETING_RULE, constraint_type=ConstraintType(r.constraint_type), weight=float(r.weight) if r.weight is not None else None, rationale=r.rationale, region=r.region, effective_from=r.effective_from, effective_to=r.effective_to, status=r.status, source_key=r.source_key, created_at=r.created_at) for r in records]

    async def disable(self, rule_id: str) -> bool:
        record = await self.session.get(MarketingRuleRecord, UUID(rule_id))
        if not record:
            return False
        record.status = RuleStatus.DISABLED.value
        await self.session.flush()
        return True

