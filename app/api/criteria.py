from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.security.workspace import scoped_task

router = APIRouter(prefix="/api")


def _explain(criteria, repository=None) -> dict[str, Any]:
    source_rules = {rid: repository.rules.get(rid) for rid in criteria.source_rule_ids} if repository else {}
    sources = []
    for rid, rule in source_rules.items():
        if rule:
            sources.append(
                {
                    "rule_id": rid,
                    "source_type": rule.source_type.value,
                    "rationale": rule.rationale,
                    "evidence_refs": rule.evidence_refs,
                    "provenance": [p.model_dump(mode="json") for p in rule.provenance],
                    "source_message_id": rule.source_message_id,
                }
            )
    return {
        "criteria_id": criteria.criteria_id,
        "criteria_hash": criteria.criteria_hash,
        "business_code": criteria.business_code,
        "region_scope": criteria.region_scope,
        "target_count": criteria.target_count,
        "hard_constraints": [item.model_dump(mode="json") for item in criteria.hard_constraints],
        "soft_constraints": [item.model_dump(mode="json") for item in criteria.soft_constraints],
        "ranking_preferences": [item.model_dump(mode="json") for item in criteria.ranking_preferences],
        "source_rule_ids": criteria.source_rule_ids,
        "sources": sources,
        "warnings": criteria.warnings,
    }


@router.get("/tasks/{task_id}/criteria")
async def get_task_criteria(task_id: str, request: Request) -> dict[str, Any]:
    scoped_task(request, task_id)
    criteria = [
        c for c in request.app.state.dependencies.rule_service.repository.criteria.values() if c.task_id == task_id
    ]
    if not criteria:
        raise HTTPException(status_code=404, detail="criteria not found")
    return _explain(
        max(criteria, key=lambda item: item.task_version), request.app.state.dependencies.rule_service.repository
    )


@router.get("/criteria/{criteria_id}/explain")
async def explain_criteria(criteria_id: str, request: Request) -> dict[str, Any]:
    criteria = request.app.state.dependencies.rule_service.repository.criteria.get(criteria_id)
    if not criteria:
        raise HTTPException(status_code=404, detail="criteria not found")
    scoped_task(request, criteria.task_id)
    return _explain(criteria, request.app.state.dependencies.rule_service.repository)
