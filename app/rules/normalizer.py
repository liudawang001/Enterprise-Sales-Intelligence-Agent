from __future__ import annotations

import re
from typing import Any

from app.rules.models import BusinessRule, ConstraintType, RuleOperator, RuleSourceType
from app.rules.registry import RuleFieldRegistry, normalize_business_code


OPERATOR_ALIASES = {"=": RuleOperator.EQ, "等于": RuleOperator.EQ, "是": RuleOperator.EQ, "至少": RuleOperator.GTE, ">=": RuleOperator.GTE, "不少于": RuleOperator.GTE, "大于": RuleOperator.GT, ">": RuleOperator.GT, "最多": RuleOperator.LTE, "不超过": RuleOperator.LTE, "<=": RuleOperator.LTE, "小于": RuleOperator.LT, "<": RuleOperator.LT, "包含": RuleOperator.CONTAINS, "排除": RuleOperator.NOT_IN}
FIELD_ALIASES = {"员工数量": "employee_count", "员工数": "employee_count", "成员数量": "member_count", "成员数": "member_count", "办公点数量": "office_count", "办公点数": "office_count", "办公地点数": "office_count", "行业": "industry", "地区": "region", "区域": "region", "跨区域": "cross_region_presence"}


class RuleNormalizationError(ValueError):
    pass


class RuleNormalizer:
    def __init__(self, registry: RuleFieldRegistry | None = None) -> None:
        self.registry = registry or RuleFieldRegistry()

    def normalize_field(self, field: str) -> str:
        normalized = FIELD_ALIASES.get(field.strip(), field.strip().lower())
        if not self.registry.exists(normalized):
            raise RuleNormalizationError(f"INVALID_RULE_FIELD: {field}")
        return normalized

    def normalize_operator(self, operator: str | RuleOperator) -> RuleOperator:
        if isinstance(operator, RuleOperator):
            return operator
        key = operator.strip().upper()
        try:
            return RuleOperator(key)
        except ValueError:
            if operator.strip() in OPERATOR_ALIASES:
                return OPERATOR_ALIASES[operator.strip()]
            raise RuleNormalizationError(f"INVALID_RULE_OPERATOR: {operator}")

    def normalize_value(self, field: str, value: Any, operator: RuleOperator | None = None) -> tuple[Any, str]:
        definition = self.registry.get(field)
        assert definition is not None
        if operator in {RuleOperator.IN, RuleOperator.NOT_IN}:
            if isinstance(value, str):
                values = [item.strip() for item in re.split(r"[,，]", value) if item.strip()]
                return values, "LIST"
            if isinstance(value, (list, tuple, set)):
                return list(value), "LIST"
            raise RuleNormalizationError("INVALID_RULE_VALUE")
        if definition.value_type == "INTEGER":
            if isinstance(value, bool):
                raise RuleNormalizationError("INVALID_RULE_VALUE")
            if isinstance(value, int):
                return value, "INTEGER"
            match = re.search(r"-?\d+", str(value).replace(",", ""))
            if match:
                return int(match.group()), "INTEGER"
            raise RuleNormalizationError("INVALID_RULE_VALUE")
        if definition.value_type == "BOOLEAN":
            if isinstance(value, bool):
                return value, "BOOLEAN"
            if str(value).lower() in {"true", "是", "有", "yes"}:
                return True, "BOOLEAN"
            if str(value).lower() in {"false", "否", "无", "no"}:
                return False, "BOOLEAN"
            raise RuleNormalizationError("INVALID_RULE_VALUE")
        if definition.value_type == "STRING" and not isinstance(value, str):
            raise RuleNormalizationError("INVALID_RULE_VALUE")
        if definition.value_type == "ENUM" and field == "company_scale" and value not in {"SMALL", "MEDIUM", "LARGE"}:
            raise RuleNormalizationError("INVALID_RULE_VALUE")
        return value, definition.value_type

    def normalize(self, rule: BusinessRule) -> BusinessRule:
        field = self.normalize_field(rule.field)
        operator = self.normalize_operator(rule.operator)
        value, value_type = self.normalize_value(field, rule.value, operator)
        definition = self.registry.get(field)
        if operator not in definition.allowed_operators:  # type: ignore[union-attr]
            raise RuleNormalizationError(f"INVALID_RULE_OPERATOR: {operator}")
        return rule.model_copy(update={"business_code": normalize_business_code(rule.business_code), "field": field, "operator": operator, "value": value, "value_type": value_type})
