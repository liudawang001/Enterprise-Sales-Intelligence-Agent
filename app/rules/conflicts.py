from __future__ import annotations

from itertools import combinations

from app.rules.models import BusinessRule, ConstraintType, RuleConflict, RuleConflictType, RuleOperator, RuleResolutionStatus, RuleSourceType


def _interval(rule: BusinessRule) -> tuple[float | None, bool, float | None, bool]:
    lower = upper = None
    lower_inc = upper_inc = True
    if rule.operator in {RuleOperator.GT, RuleOperator.GTE}:
        lower, lower_inc = float(rule.value), rule.operator == RuleOperator.GTE
    elif rule.operator in {RuleOperator.LT, RuleOperator.LTE}:
        upper, upper_inc = float(rule.value), rule.operator == RuleOperator.LTE
    elif rule.operator == RuleOperator.EQ:
        lower = upper = float(rule.value) if isinstance(rule.value, (int, float)) else None
    return lower, lower_inc, upper, upper_inc


class RuleConflictService:
    def detect(self, rules: list[BusinessRule]) -> list[RuleConflict]:
        conflicts: list[RuleConflict] = []
        for left, right in combinations(rules, 2):
            if left.field != right.field:
                continue
            if left.source_key and left.source_key == right.source_key or left.field == right.field and left.operator == right.operator and left.value == right.value:
                conflicts.append(RuleConflict(conflict_type=RuleConflictType.DUPLICATE, rule_ids=[left.rule_id, right.rule_id], field=left.field, blocking=False, explanation="重复规则"))
                continue
            blocking = left.constraint_type == ConstraintType.HARD and right.constraint_type == ConstraintType.HARD
            if {left.operator, right.operator} <= {RuleOperator.IN, RuleOperator.NOT_IN} and left.value == right.value and left.operator != right.operator:
                conflicts.append(RuleConflict(conflict_type=RuleConflictType.OFFICIAL_USER_CONFLICT if blocking and {left.source_type, right.source_type} == {RuleSourceType.OFFICIAL_REQUIREMENT, RuleSourceType.USER_REQUIREMENT} else RuleConflictType.DIRECT_CONFLICT, rule_ids=[left.rule_id, right.rule_id], field=left.field, blocking=blocking, explanation="Include 与 Exclude 条件互斥"))
                continue
            if left.operator == right.operator == RuleOperator.EQ and left.value != right.value:
                official_user = {left.source_type, right.source_type} == {RuleSourceType.OFFICIAL_REQUIREMENT, RuleSourceType.USER_REQUIREMENT}
                conflicts.append(RuleConflict(conflict_type=RuleConflictType.OFFICIAL_USER_CONFLICT if blocking and official_user else RuleConflictType.DIRECT_CONFLICT, rule_ids=[left.rule_id, right.rule_id], field=left.field, blocking=blocking, explanation="同一字段要求不同且不可同时满足"))
                continue
            if left.operator in {RuleOperator.GT, RuleOperator.GTE, RuleOperator.LT, RuleOperator.LTE, RuleOperator.EQ} and right.operator in {RuleOperator.GT, RuleOperator.GTE, RuleOperator.LT, RuleOperator.LTE, RuleOperator.EQ}:
                l1, li1, u1, ui1 = _interval(left); l2, li2, u2, ui2 = _interval(right)
                low = max(x for x in (l1, l2) if x is not None) if any(x is not None for x in (l1, l2)) else None
                high = min(x for x in (u1, u2) if x is not None) if any(x is not None for x in (u1, u2)) else None
                empty = low is not None and high is not None and (low > high or (low == high and not (li1 and li2 and ui1 and ui2)))
                if empty:
                    conflicts.append(RuleConflict(conflict_type=RuleConflictType.OFFICIAL_USER_CONFLICT if blocking and {left.source_type, right.source_type} == {RuleSourceType.OFFICIAL_REQUIREMENT, RuleSourceType.USER_REQUIREMENT} else RuleConflictType.DIRECT_CONFLICT, rule_ids=[left.rule_id, right.rule_id], field=left.field, blocking=blocking, explanation="数值范围没有交集"))
                elif left.constraint_type == ConstraintType.HARD and right.constraint_type == ConstraintType.HARD:
                    conflicts.append(RuleConflict(conflict_type=RuleConflictType.NARROWER, rule_ids=[left.rule_id, right.rule_id], field=left.field, blocking=False, explanation="条件兼容，较严格条件取交集"))
            elif left.constraint_type == ConstraintType.SOFT and right.constraint_type == ConstraintType.SOFT and left.value != right.value:
                conflicts.append(RuleConflict(conflict_type=RuleConflictType.SOFT_CONFLICT, rule_ids=[left.rule_id, right.rule_id], field=left.field, blocking=False, explanation="软偏好存在竞争"))
        return conflicts

    def resolve(self, rules: list[BusinessRule], conflicts: list[RuleConflict]) -> tuple[list[BusinessRule], list[BusinessRule]]:
        suppressed: set[str] = set()
        for conflict in conflicts:
            if conflict.conflict_type == RuleConflictType.DUPLICATE:
                # Compiler coalesces duplicates and retains all provenance IDs.
                continue
            elif conflict.conflict_type in {RuleConflictType.OFFICIAL_USER_CONFLICT, RuleConflictType.DIRECT_CONFLICT} and conflict.blocking:
                continue
            elif conflict.conflict_type == RuleConflictType.DIRECT_CONFLICT:
                pair = [next(r for r in rules if r.rule_id == rid) for rid in conflict.rule_ids]
                soft = [r for r in pair if r.constraint_type == ConstraintType.SOFT]
                if soft:
                    suppressed.add(min(soft, key=lambda r: (r.source_type == RuleSourceType.USER_REQUIREMENT, r.weight or 0)).rule_id)
            elif conflict.conflict_type in {RuleConflictType.SOFT_CONFLICT, RuleConflictType.NARROWER}:
                pair = [next(r for r in rules if r.rule_id == rid) for rid in conflict.rule_ids]
                if conflict.conflict_type == RuleConflictType.NARROWER and all(r.operator in {RuleOperator.GTE, RuleOperator.GT} for r in pair):
                    loser = min(pair, key=lambda r: float(r.value))
                elif conflict.conflict_type == RuleConflictType.NARROWER and all(r.operator in {RuleOperator.LTE, RuleOperator.LT} for r in pair):
                    loser = max(pair, key=lambda r: float(r.value))
                else:
                    loser = min(pair, key=lambda r: (r.source_type == RuleSourceType.USER_REQUIREMENT, r.weight or 0), default=pair[-1])
                if conflict.conflict_type == RuleConflictType.SOFT_CONFLICT:
                    suppressed.add(loser.rule_id)
        included, suppressed_rules = [], []
        for rule in rules:
            if rule.rule_id in suppressed:
                suppressed_rules.append(rule.model_copy(update={"resolution_status": RuleResolutionStatus.SUPPRESSED, "suppression_reason": "SUPPRESSED_BY_USER_REQUIREMENT"}))
            else:
                included.append(rule.model_copy(update={"resolution_status": RuleResolutionStatus.INCLUDED}))
        return included, suppressed_rules
