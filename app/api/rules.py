from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.rules.models import BusinessRule, ConstraintType, RuleOperator, RuleProvenance, RuleSourceType, RuleStatus

router = APIRouter(prefix="/api")


class MarketingRuleRequest(BaseModel):
    field: str
    operator: RuleOperator
    value: Any
    value_type: str = "AUTO"
    constraint_type: ConstraintType = ConstraintType.SOFT
    weight: float | None = None
    region: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    rationale: str | None = None


@router.get("/businesses/{business_code}/marketing-rules")
async def list_marketing_rules(business_code: str, request: Request, region: str | None = None) -> list[dict[str, Any]]:
    return [rule.model_dump(mode="json") for rule in request.app.state.dependencies.rule_service.repository.list_marketing(business_code, region)]


@router.post("/businesses/{business_code}/marketing-rules")
async def create_marketing_rule(business_code: str, payload: MarketingRuleRequest, request: Request) -> dict[str, Any]:
    service = request.app.state.dependencies.rule_service
    rule = BusinessRule(business_code=business_code, source_type=RuleSourceType.MARKETING_RULE, **payload.model_dump())
    rule = rule.model_copy(update={"source_key": f"marketing:{rule.rule_id}", "provenance": [RuleProvenance(source_type=RuleSourceType.MARKETING_RULE, marketing_rule_id=rule.rule_id)]})
    try:
        rule = service.normalizer.normalize(rule)
        service.validator.validate(rule)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return service.repository.save_marketing(rule).model_dump(mode="json")


@router.patch("/marketing-rules/{rule_id}/disable")
async def disable_marketing_rule(rule_id: str, request: Request) -> dict[str, Any]:
    service = request.app.state.dependencies.rule_service
    rule = service.repository.marketing_rules.get(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="marketing rule not found")
    updated = rule.model_copy(update={"status": RuleStatus.DISABLED})
    service.repository.marketing_rules[rule_id] = updated
    return updated.model_dump(mode="json")
