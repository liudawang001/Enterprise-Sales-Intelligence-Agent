from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from app.criteria.models import CompiledConstraint, LeadCriteria, RankingPreference
from app.rules.models import BusinessRule, ConstraintType, RuleOperator, RuleSourceType


class CriteriaCompiler:
    @staticmethod
    def _constraint(group: list[BusinessRule], selected: BusinessRule | None = None) -> CompiledConstraint:
        winner = selected or group[0]
        return CompiledConstraint(
            field=winner.field,
            operator=winner.operator,
            value=winner.value,
            source_rule_ids=sorted({r.rule_id for r in group}),
            rationale="；".join(dict.fromkeys(filter(None, (r.rationale for r in group)))) or None,
        )

    def _compile_hard(self, rules: list[BusinessRule]) -> list[CompiledConstraint]:
        by_field: dict[str, list[BusinessRule]] = defaultdict(list)
        for rule in rules:
            by_field[rule.field].append(rule)
        compiled: list[CompiledConstraint] = []
        for field in sorted(by_field):
            field_rules = by_field[field]
            numeric = [r for r in field_rules if r.operator in {RuleOperator.GT, RuleOperator.GTE, RuleOperator.LT, RuleOperator.LTE} and isinstance(r.value, (int, float))]
            lowers = [r for r in numeric if r.operator in {RuleOperator.GT, RuleOperator.GTE}]
            uppers = [r for r in numeric if r.operator in {RuleOperator.LT, RuleOperator.LTE}]
            consumed = {r.rule_id for r in numeric}
            if lowers:
                winner = max(lowers, key=lambda r: (float(r.value), r.operator == RuleOperator.GT))
                compiled.append(self._constraint(lowers, winner))
            if uppers:
                winner = min(uppers, key=lambda r: (float(r.value), r.operator == RuleOperator.LTE))
                compiled.append(self._constraint(uppers, winner))
            exact: dict[tuple[str, str], list[BusinessRule]] = defaultdict(list)
            for rule in field_rules:
                if rule.rule_id not in consumed:
                    exact[(rule.operator.value, json.dumps(rule.value, sort_keys=True, ensure_ascii=False))].append(rule)
            for key in sorted(exact):
                compiled.append(self._constraint(exact[key]))
        return compiled

    def compile(self, *, task_id: str, task_version: int, business_code: str, region: str, target_count: int, rules: list[BusinessRule], required_fields: list[str] | None = None, warnings: list[str] | None = None) -> LeadCriteria:
        hard_rules = [r for r in rules if r.constraint_type == ConstraintType.HARD and r.status.value == "ACTIVE"]
        hard, soft = self._compile_hard(hard_rules), []
        grouped: dict[tuple[str, str, str], list[BusinessRule]] = defaultdict(list)
        for rule in rules:
            if rule.constraint_type != ConstraintType.SOFT or rule.status.value != "ACTIVE":
                continue
            grouped[(rule.field, rule.operator.value, json.dumps(rule.value, sort_keys=True, ensure_ascii=False))].append(rule)
        for (field, operator, value_json), group in grouped.items():
            value = json.loads(value_json)
            constraint = CompiledConstraint(field=field, operator=operator, value=value, source_rule_ids=sorted({r.rule_id for r in group}), rationale="；".join(dict.fromkeys(filter(None, (r.rationale for r in group)))) or None)
            soft.append(constraint)
        prefs: list[RankingPreference] = []
        soft.sort(key=lambda item: (item.field, item.operator.value, repr(item.value)))
        weighted: list[tuple[CompiledConstraint, float]] = []
        for constraint in soft:
            source_rules = [r for r in rules if r.rule_id in constraint.source_rule_ids]
            weight = max((r.weight if r.weight is not None else (1.0 if r.source_type == RuleSourceType.USER_REQUIREMENT else 0.4 if r.source_type == RuleSourceType.MARKETING_RULE else 0.3)) for r in source_rules)
            weighted.append((constraint, weight))
        total_weight = sum(weight for _, weight in weighted) or 1.0
        for constraint, weight in weighted:
            prefs.append(RankingPreference(field=constraint.field, operator=constraint.operator, value=constraint.value, normalized_weight=round(weight / total_weight, 6), source_rule_ids=constraint.source_rule_ids))
        criteria = LeadCriteria(task_id=task_id, task_version=task_version, business_code=business_code, region_scope=[region], target_count=target_count, hard_constraints=hard, soft_constraints=soft, required_fields=required_fields or ["company_name", "phone", "address"], ranking_preferences=prefs, source_rule_ids=sorted({r.rule_id for r in rules if r.constraint_type != ConstraintType.INFO}), warnings=warnings or [])
        criteria.criteria_hash = self.hash(criteria)
        return criteria

    @staticmethod
    def hash(criteria: LeadCriteria) -> str:
        payload = criteria.model_dump(mode="json", exclude={"criteria_id", "created_at", "criteria_hash"})
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
