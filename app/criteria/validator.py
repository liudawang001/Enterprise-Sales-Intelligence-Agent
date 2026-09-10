from itertools import combinations

from app.criteria.models import CompiledConstraint, LeadCriteria
from app.rules.models import RuleOperator
from app.rules.registry import BUSINESS_CATALOG, RuleFieldRegistry


class CriteriaValidationError(ValueError):
    pass


def _incompatible(left: CompiledConstraint, right: CompiledConstraint) -> bool:
    if left.field != right.field:
        return False
    if left.operator == right.operator == RuleOperator.EQ:
        return left.value != right.value
    if {left.operator, right.operator} == {RuleOperator.IN, RuleOperator.NOT_IN}:
        return left.value == right.value
    lower = next((item for item in (left, right) if item.operator in {RuleOperator.GT, RuleOperator.GTE}), None)
    upper = next((item for item in (left, right) if item.operator in {RuleOperator.LT, RuleOperator.LTE}), None)
    if lower and upper and isinstance(lower.value, (int, float)) and isinstance(upper.value, (int, float)):
        return lower.value > upper.value or (lower.value == upper.value and (lower.operator == RuleOperator.GT or upper.operator == RuleOperator.LT))
    return False


def validate_criteria(criteria: LeadCriteria) -> LeadCriteria:
    if criteria.business_code not in BUSINESS_CATALOG or not criteria.region_scope or criteria.target_count <= 0:
        raise CriteriaValidationError("CRITERIA_VALIDATION_FAILED")
    registry = RuleFieldRegistry()
    constraints = criteria.hard_constraints + criteria.soft_constraints
    for constraint in constraints:
        definition = registry.get(constraint.field)
        if definition is None or constraint.operator not in definition.allowed_operators:
            raise CriteriaValidationError("CRITERIA_VALIDATION_FAILED")
        if not constraint.source_rule_ids:
            raise CriteriaValidationError("source_rule_ids must not be empty")
    if any(_incompatible(left, right) for left, right in combinations(criteria.hard_constraints, 2)):
        raise CriteriaValidationError("Hard Constraint conflict")
    if not criteria.source_rule_ids and constraints:
        raise CriteriaValidationError("source_rule_ids must not be empty")
    for preference in criteria.ranking_preferences:
        if not preference.source_rule_ids or not 0 <= preference.normalized_weight <= 1:
            raise CriteriaValidationError("Soft Weight must be normalized")
    return criteria

