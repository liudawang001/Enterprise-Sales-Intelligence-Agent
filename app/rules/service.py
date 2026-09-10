from __future__ import annotations

from datetime import date
from typing import Any

from app.criteria.compiler import CriteriaCompiler
from app.criteria.models import LeadCriteria
from app.criteria.validator import validate_criteria
from app.rules.conflicts import RuleConflictService
from app.rules.models import BusinessRule, ConstraintType, RuleModality, RuleProvenance, RuleSourceType, RuleStatus
from app.rules.normalizer import RuleNormalizer
from app.rules.registry import RuleFieldRegistry, normalize_business_code
from app.rules.validator import RuleValidator
from app.rules.extractor import OfficialRuleExtractor
from app.rules.suggestion import ModelSuggestionGenerator


class InMemoryRuleRepository:
    def __init__(self) -> None:
        self.rules: dict[str, BusinessRule] = {}
        self.marketing_rules: dict[str, BusinessRule] = {}
        self.criteria: dict[str, LeadCriteria] = {}
        self.evidence: dict[str, dict[str, Any]] = {}
        self.conflicts: dict[str, Any] = {}

    def upsert(self, rule: BusinessRule) -> BusinessRule:
        if rule.source_key:
            existing = next((item for item in self.rules.values() if item.source_key == rule.source_key), None)
            if existing:
                return existing
        self.rules[rule.rule_id] = rule
        return rule

    def list_marketing(self, business_code: str, region: str | None = None, as_of: date | None = None) -> list[BusinessRule]:
        today = as_of or date.today()
        return [r for r in self.marketing_rules.values() if r.business_code == normalize_business_code(business_code) and r.status == RuleStatus.ACTIVE and (not r.region or not region or r.region == region) and (not r.effective_from or r.effective_from <= today) and (not r.effective_to or r.effective_to >= today)]

    def save_marketing(self, rule: BusinessRule) -> BusinessRule:
        saved = self.upsert(rule)
        self.marketing_rules[saved.rule_id] = saved
        return saved

    def save_evidence(self, chunks: list[dict[str, Any]]) -> list[str]:
        for chunk in chunks:
            self.evidence[str(chunk["chunk_id"])] = chunk
        return [str(chunk["chunk_id"]) for chunk in chunks]

    def get_evidence(self, ids: list[str]) -> list[dict[str, Any]]:
        return [self.evidence[item] for item in ids if item in self.evidence]

    def get_rules(self, ids: list[str]) -> list[BusinessRule]:
        return [self.rules[item] for item in ids if item in self.rules]

    def save_conflicts(self, conflicts: list[Any]) -> list[str]:
        for conflict in conflicts:
            self.conflicts[conflict.conflict_id] = conflict
        return [conflict.conflict_id for conflict in conflicts]

    def get_conflicts(self, ids: list[str]) -> list[Any]:
        return [self.conflicts[item] for item in ids if item in self.conflicts]

    def save_criteria(self, criteria: LeadCriteria) -> LeadCriteria:
        existing = next((c for c in self.criteria.values() if c.criteria_hash == criteria.criteria_hash and c.task_id == criteria.task_id and c.task_version == criteria.task_version), None)
        if existing:
            return existing
        self.criteria[criteria.criteria_id] = criteria
        return criteria


class BusinessRuleService:
    def __init__(self, repository: InMemoryRuleRepository | None = None) -> None:
        self.repository = repository or InMemoryRuleRepository()
        self.registry = RuleFieldRegistry()
        self.normalizer = RuleNormalizer(self.registry)
        self.validator = RuleValidator(self.registry)
        self.conflicts = RuleConflictService()
        self.compiler = CriteriaCompiler()
        self.official_extractor = OfficialRuleExtractor()
        self.suggestion_generator = ModelSuggestionGenerator(registry=self.registry)

    def seed_demo_rules(self) -> None:
        demos = [
            ("GROUP_VNET", "office_count", "GTE", 2, 0.20, "优先关注多个办公地点企业"),
            ("GROUP_VNET", "cross_region_presence", "EQ", True, 0.15, "跨区域内部通信需求更相关"),
            ("ENTERPRISE_DEDICATED_LINE", "company_scale", "IN", ["MEDIUM", "LARGE"], 0.20, "中大型企业更适合专线"),
        ]
        for business, field, operator, value, weight, rationale in demos:
            rule = BusinessRule(business_code=business, field=field, operator=operator, value=value, value_type="AUTO", source_type=RuleSourceType.MARKETING_RULE, constraint_type=ConstraintType.SOFT, weight=weight, confidence=1.0, rationale=rationale, source_key=f"demo:{business}:{field}:{operator}:{value}")
            rule = rule.model_copy(update={"provenance": [RuleProvenance(source_type=RuleSourceType.MARKETING_RULE, marketing_rule_id=rule.rule_id)]})
            try: rule = self.normalizer.normalize(rule)
            except Exception: continue
            self.repository.save_marketing(rule)

    def official_rules_from_evidence(self, business_code: str, extracted: list[Any], evidence: list[dict[str, Any]]) -> tuple[list[BusinessRule], list[str]]:
        by_id = {str(item["chunk_id"]): item for item in evidence}
        result, warnings = [], []
        for item in extracted:
            refs = list(item.evidence_chunk_ids)
            if not refs or not all(ref in by_id for ref in refs):
                warnings.append("OFFICIAL_RULE_MISSING_EVIDENCE")
                continue
            modality = item.modality
            ctype = ConstraintType.HARD if modality == RuleModality.REQUIRED else ConstraintType.SOFT if modality == RuleModality.RECOMMENDED else ConstraintType.INFO
            prov = [RuleProvenance(source_type=RuleSourceType.OFFICIAL_REQUIREMENT, document_id=str(by_id[ref].get("document_id")), chunk_id=ref, page_start=by_id[ref].get("page_start"), page_end=by_id[ref].get("page_end"), evidence_text=by_id[ref].get("content")) for ref in refs]
            rule = BusinessRule(business_code=business_code, field=item.field, operator=item.operator, value=item.value, value_type=item.value_type or "AUTO", source_type=RuleSourceType.OFFICIAL_REQUIREMENT, constraint_type=ctype, confidence=item.confidence, rationale=item.rationale, evidence_refs=refs, provenance=prov, modality=modality, source_key=f"official:{business_code}:{':'.join(refs)}:{item.field}:{item.operator}:{item.value}")
            try:
                rule = self.normalizer.normalize(rule); self.validator.validate(rule); result.append(self.repository.upsert(rule))
            except Exception as exc: warnings.append(str(exc))
        return result, warnings

    def compile(self, *, task_id: str, task_version: int, business_code: str, region: str, target_count: int, rules: list[BusinessRule], required_fields: list[str] | None = None, warnings: list[str] | None = None) -> LeadCriteria:
        criteria = self.compiler.compile(task_id=task_id, task_version=task_version, business_code=normalize_business_code(business_code), region=region, target_count=target_count, rules=rules, required_fields=required_fields, warnings=warnings)
        validate_criteria(criteria)
        return self.repository.save_criteria(criteria)
