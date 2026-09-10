from app.criteria.evaluator import DefaultCriteriaEvaluator
from app.rules.conflicts import RuleConflictService
from datetime import date, timedelta

import pytest

from app.rules.models import BusinessRule, ConstraintType, ModelSuggestion, ModelSuggestionResult, RuleModality, RuleOperator, RuleSourceType, RuleStatus
from app.rules.service import BusinessRuleService
from app.rules.suggestion import ModelSuggestionGenerator
from app.rules.validator import RuleValidationError


def rule(source, ctype, op, value, *, field="member_count", evidence=False):
    return BusinessRule(business_code="GROUP_VNET", field=field, operator=op, value=value, value_type="AUTO", source_type=source, constraint_type=ctype, evidence_refs=["chunk-1"] if evidence else [])


def test_normalization_and_official_evidence_gate():
    service = BusinessRuleService()
    normalized = service.normalizer.normalize(rule(RuleSourceType.USER_REQUIREMENT, ConstraintType.HARD, "至少", "100人", field="员工数量"))
    assert (normalized.field, normalized.operator, normalized.value) == ("employee_count", RuleOperator.GTE, 100)
    accepted, warnings = service.official_rules_from_evidence("GROUP_VNET", [type("X", (), {"field": "member_count", "operator": RuleOperator.GTE, "value": 10, "value_type": "INTEGER", "modality": RuleModality.REQUIRED, "confidence": 1.0, "rationale": None, "evidence_chunk_ids": []})()], [])
    assert accepted == [] and warnings


def test_official_user_conflict_is_blocking():
    conflicts = RuleConflictService().detect([rule(RuleSourceType.OFFICIAL_REQUIREMENT, ConstraintType.HARD, RuleOperator.GTE, 10, evidence=True), rule(RuleSourceType.USER_REQUIREMENT, ConstraintType.HARD, RuleOperator.LT, 5)])
    assert conflicts[0].blocking is True
    assert conflicts[0].conflict_type.value == "OFFICIAL_USER_CONFLICT"


def test_criteria_hash_and_mock_execution():
    service = BusinessRuleService(); service.seed_demo_rules()
    criteria = service.compile(task_id="t1", task_version=1, business_code="GROUP_VNET", region="上海松江", target_count=50, rules=[rule(RuleSourceType.USER_REQUIREMENT, ConstraintType.HARD, RuleOperator.EQ, "上海松江", field="region")] + service.repository.list_marketing("GROUP_VNET"))
    assert criteria.criteria_hash and criteria.criteria_id and criteria.soft_constraints
    evaluator = DefaultCriteriaEvaluator()
    assert evaluator.matches_hard_constraints({"region": "上海松江"}, criteria)
    assert evaluator.preference_score({"office_count": 3}, criteria) > evaluator.preference_score({"office_count": 1}, criteria)
    assert abs(sum(item.normalized_weight for item in criteria.ranking_preferences) - 1.0) < 0.00001


def test_hard_range_uses_intersection_and_keeps_provenance():
    service = BusinessRuleService()
    official = rule(RuleSourceType.OFFICIAL_REQUIREMENT, ConstraintType.HARD, RuleOperator.GTE, 10, evidence=True)
    user = rule(RuleSourceType.USER_REQUIREMENT, ConstraintType.HARD, RuleOperator.GTE, 50)
    criteria = service.compile(task_id="t2", task_version=1, business_code="GROUP_VNET", region="上海松江", target_count=10, rules=[official, user])
    assert len(criteria.hard_constraints) == 1
    assert criteria.hard_constraints[0].value == 50
    assert set(criteria.hard_constraints[0].source_rule_ids) == {official.rule_id, user.rule_id}


def test_in_value_is_normalized_to_list():
    service = BusinessRuleService()
    normalized = service.normalizer.normalize(rule(RuleSourceType.USER_REQUIREMENT, ConstraintType.HARD, RuleOperator.IN, "制造业，物流", field="industry"))
    assert normalized.value == ["制造业", "物流"]


def test_model_suggestion_is_grounded_registered_and_limited():
    class Runnable:
        def invoke(self, _payload):
            suggestions = [ModelSuggestion(field="industry", operator="EQ", value="制造业", rationale="evidence", confidence=0.8, evidence_refs=["c1"]) for _ in range(6)]
            suggestions.append(ModelSuggestion(field="unknown", operator="EQ", value="x", rationale="evidence", confidence=0.8, evidence_refs=["c1"]))
            return ModelSuggestionResult(suggestions=suggestions)

    class LLM:
        def with_structured_output(self, _schema):
            return Runnable()

    assert len(ModelSuggestionGenerator(LLM()).generate({})) == 5
    service = BusinessRuleService()
    invalid = rule(RuleSourceType.MODEL_SUGGESTION, ConstraintType.HARD, RuleOperator.EQ, "制造业", field="industry")
    with pytest.raises(RuleValidationError):
        service.validator.validate(invalid)


def test_marketing_filters_and_snapshot_idempotency():
    service = BusinessRuleService()
    today = date.today()
    active = rule(RuleSourceType.MARKETING_RULE, ConstraintType.SOFT, RuleOperator.EQ, "制造业", field="industry").model_copy(update={"region": "上海松江", "effective_from": today - timedelta(days=1), "effective_to": today + timedelta(days=1)})
    disabled = active.model_copy(update={"rule_id": "disabled", "source_key": "disabled", "status": RuleStatus.DISABLED})
    service.repository.save_marketing(active); service.repository.save_marketing(disabled)
    assert service.repository.list_marketing("GROUP_VNET", "上海松江") == [active]
    first = service.compile(task_id="stable", task_version=1, business_code="GROUP_VNET", region="上海松江", target_count=10, rules=[active])
    second = service.compile(task_id="stable", task_version=1, business_code="GROUP_VNET", region="上海松江", target_count=10, rules=[active])
    assert first.criteria_hash == second.criteria_hash
    assert first.criteria_id == second.criteria_id
