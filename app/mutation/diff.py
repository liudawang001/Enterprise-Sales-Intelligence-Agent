from __future__ import annotations

from app.criteria.diff import diff_criteria
from app.criteria.models import CompiledConstraint, LeadCriteria, RankingPreference
from app.domain.task import LeadTask
from app.rules.models import RuleOperator
from app.rules.registry import normalize_business_code


def criteria_from_task(task: LeadTask) -> LeadCriteria:
    hard: list[CompiledConstraint] = []
    soft: list[CompiledConstraint] = []
    ranking: list[RankingPreference] = []
    for item in task.constraints:
        if not item.get("field") or item.get("value") is None:
            continue
        constraint = CompiledConstraint(field=item["field"], operator=RuleOperator(item.get("operator", "EQ")), value=item["value"])
        if item.get("constraint_type", "HARD") == "SOFT":
            soft.append(constraint)
            ranking.append(RankingPreference(field=constraint.field, operator=constraint.operator, value=constraint.value, normalized_weight=1.0))
        else:
            hard.append(constraint)
    return LeadCriteria(
        task_id=task.task_id,
        task_version=task.version,
        business_code=normalize_business_code(task.business or ""),
        region_scope=[task.region] if task.region else [],
        target_count=task.target_count or 1,
        hard_constraints=hard,
        soft_constraints=soft,
        required_fields=task.required_fields,
        ranking_preferences=ranking,
    )


def calculate_criteria_diff(before: LeadTask, after: LeadTask):
    return diff_criteria(criteria_from_task(before), criteria_from_task(after))
