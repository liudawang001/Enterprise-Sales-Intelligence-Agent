from __future__ import annotations

from datetime import date

from app.rules.models import BusinessRule, ConstraintType, RuleSourceType, RuleStatus
from app.rules.registry import BUSINESS_CATALOG, RuleFieldRegistry


class RuleValidationError(ValueError):
    pass


class RuleValidator:
    def __init__(self, registry: RuleFieldRegistry | None = None) -> None:
        self.registry = registry or RuleFieldRegistry()

    def validate(self, rule: BusinessRule, *, today: date | None = None) -> BusinessRule:
        if rule.business_code not in BUSINESS_CATALOG:
            raise RuleValidationError("INVALID_BUSINESS")
        definition = self.registry.get(rule.field)
        if definition is None:
            raise RuleValidationError("INVALID_RULE_FIELD")
        if rule.operator not in definition.allowed_operators:
            raise RuleValidationError("INVALID_RULE_OPERATOR")
        if rule.source_type == RuleSourceType.OFFICIAL_REQUIREMENT and not rule.evidence_refs:
            raise RuleValidationError("OFFICIAL_RULE_MISSING_EVIDENCE")
        if rule.source_type == RuleSourceType.MODEL_SUGGESTION and rule.constraint_type != ConstraintType.SOFT:
            raise RuleValidationError("MODEL_SUGGESTION_MUST_BE_SOFT")
        if rule.source_type == RuleSourceType.MODEL_SUGGESTION and not rule.evidence_refs:
            raise RuleValidationError("MODEL_SUGGESTION_MISSING_EVIDENCE")
        if rule.source_type == RuleSourceType.MARKETING_RULE and rule.constraint_type == ConstraintType.HARD:
            raise RuleValidationError("MARKETING_RULE_MUST_NOT_BE_HARD")
        if rule.status != RuleStatus.ACTIVE:
            raise RuleValidationError("RULE_NOT_ACTIVE")
        check_date = today or date.today()
        if rule.effective_from and rule.effective_from > check_date or rule.effective_to and rule.effective_to < check_date:
            raise RuleValidationError("RULE_EXPIRED")
        if rule.modality:
            expected = {"REQUIRED": ConstraintType.HARD, "RECOMMENDED": ConstraintType.SOFT, "INFORMATIONAL": ConstraintType.INFO}[rule.modality.value]
            if rule.constraint_type != expected:
                raise RuleValidationError("INVALID_RULE_MODALITY")
        return rule
