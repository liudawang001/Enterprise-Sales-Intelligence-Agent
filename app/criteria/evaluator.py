from __future__ import annotations

from typing import Any, Protocol

from app.criteria.models import LeadCriteria
from app.rules.models import RuleOperator
from app.research.models import FilterOutcome


class CriteriaEvaluator(Protocol):
    def matches_hard_constraints(self, enterprise: dict[str, Any], criteria: LeadCriteria) -> bool: ...
    def preference_score(self, enterprise: dict[str, Any], criteria: LeadCriteria) -> float: ...


def _matches(value: Any, operator: RuleOperator, expected: Any) -> bool:
    if operator == RuleOperator.EQ: return value == expected
    if operator == RuleOperator.NE: return value != expected
    if operator == RuleOperator.GT: return value is not None and value > expected
    if operator == RuleOperator.GTE: return value is not None and value >= expected
    if operator == RuleOperator.LT: return value is not None and value < expected
    if operator == RuleOperator.LTE: return value is not None and value <= expected
    if operator == RuleOperator.IN: return value in expected
    if operator == RuleOperator.NOT_IN: return value not in expected
    if operator == RuleOperator.CONTAINS: return expected in value if value is not None else False
    if operator == RuleOperator.EXISTS: return value is not None
    if operator == RuleOperator.NOT_EXISTS: return value is None
    return False


class DefaultCriteriaEvaluator:
    def evaluate_hard_constraints(self, enterprise: dict[str, Any], criteria: LeadCriteria) -> FilterOutcome:
        unknown = False
        for constraint in criteria.hard_constraints:
            value = enterprise.get(constraint.field)
            if constraint.field == "has_office_in":
                locations = enterprise.get("locations")
                value = locations if locations else ([enterprise.get("address")] if enterprise.get("address") else None)
            if value is None:
                unknown = True
                continue
            if not _matches(value, constraint.operator, constraint.value):
                return FilterOutcome.NO_MATCH
        return FilterOutcome.UNKNOWN if unknown else FilterOutcome.MATCH

    def matches_hard_constraints(self, enterprise: dict[str, Any], criteria: LeadCriteria) -> bool:
        return self.evaluate_hard_constraints(enterprise, criteria) == FilterOutcome.MATCH

    def preference_score(self, enterprise: dict[str, Any], criteria: LeadCriteria) -> float:
        return sum(pref.normalized_weight for pref in criteria.ranking_preferences if _matches(enterprise.get(pref.field), pref.operator, pref.value))
