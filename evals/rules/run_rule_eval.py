import json
from pathlib import Path

from app.rules.conflicts import RuleConflictService
from app.rules.models import BusinessRule, ConstraintType, OfficialRuleExtractionInput, RuleEvidenceChunk, RuleOperator, RuleSourceType
from app.rules.service import BusinessRuleService


def _rule(payload, business="GROUP_VNET"):
    source = RuleSourceType(payload["source_type"])
    return BusinessRule(business_code=business, field=payload["field"], operator=RuleOperator(payload["operator"]), value=payload["value"], value_type="AUTO", source_type=source, constraint_type=ConstraintType(payload["constraint_type"]), evidence_refs=["c"] if source == RuleSourceType.OFFICIAL_REQUIREMENT else [])


def main() -> None:
    cases = [json.loads(line) for line in Path("evals/rules/dataset.jsonl").read_text().splitlines() if line.strip()]
    service = BusinessRuleService()
    extraction_total = extraction_exact = evidence_binding = 0
    conflict_total = conflict_ok = 0
    criteria_total = criteria_valid = 0
    for case in cases:
        if case["type"] == "extraction":
            extraction_total += 1
            payload = OfficialRuleExtractionInput(business=case["business"], task_requirements={}, evidence_chunks=[RuleEvidenceChunk.model_validate(item) for item in case["evidence"]])
            extracted = service.official_extractor.extract(payload)
            rules, _ = service.official_rules_from_evidence(case["business"], extracted.rules, case["evidence"])
            got = [(r.field, r.operator.value, r.value, r.constraint_type.value) for r in rules]
            exp = [(e["field"], e["operator"], e["value"], e["constraint_type"]) for e in case["expected"]]
            extraction_exact += int(got == exp)
            evidence_binding += int(all(r.evidence_refs for r in rules))
        elif case["type"] == "conflict":
            conflict_total += 1
            conflicts = RuleConflictService().detect([_rule(r) for r in case["rules"]])
            conflict_ok += int(any(c.blocking for c in conflicts) == case["expected_blocking"])
        elif case["type"] == "criteria":
            criteria_total += 1
            criteria = service.compile(task_id=case["id"], task_version=1, business_code=case["business"], region=case["region"], target_count=case["target_count"], rules=[_rule(r, case["business"]) for r in case["rules"]])
            criteria_valid += int(bool(criteria.criteria_hash) == case["expected_valid"])
    print(json.dumps({
        "rule_exact_match": extraction_exact / extraction_total if extraction_total else None,
        "evidence_binding": evidence_binding / extraction_total if extraction_total else None,
        "conflict_accuracy": conflict_ok / conflict_total if conflict_total else None,
        "criteria_validity": criteria_valid / criteria_total if criteria_total else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
