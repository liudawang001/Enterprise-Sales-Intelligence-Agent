"""Generate deterministic, synthetic Phase 3 datasets."""
from __future__ import annotations

import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def rule_eval_rows() -> list[dict]:
    rows = []
    for index in range(30):
        value = 10 + index
        rows.append({"id": f"rule-{index + 1:03d}", "type": "extraction", "business": "GROUP_VNET", "evidence": [{"chunk_id": f"chunk-{index + 1:03d}", "document_id": "demo-vnet", "content": f"集团V网办理原则上成员数量不少于{value}。"}], "expected": [{"field": "member_count", "operator": "GTE", "value": value, "constraint_type": "HARD"}]})
    for index in range(20):
        blocking = index % 2 == 0
        rows.append({"id": f"conflict-{index + 1:03d}", "type": "conflict", "rules": [{"field": "member_count", "operator": "GTE", "value": 10, "source_type": "OFFICIAL_REQUIREMENT", "constraint_type": "HARD"}, {"field": "member_count", "operator": "LT" if blocking else "GTE", "value": 5 if blocking else 20, "source_type": "USER_REQUIREMENT", "constraint_type": "HARD"}], "expected_blocking": blocking})
    for index in range(20):
        rows.append({"id": f"criteria-{index + 1:03d}", "type": "criteria", "business": "GROUP_VNET", "region": "上海松江", "target_count": index + 1, "rules": [{"field": "region", "operator": "EQ", "value": "上海松江", "source_type": "USER_REQUIREMENT", "constraint_type": "HARD"}, {"field": "industry", "operator": "EQ", "value": "制造业", "source_type": "USER_REQUIREMENT", "constraint_type": "SOFT"}], "expected_valid": True})
    return rows


def synthetic_customers() -> list[dict]:
    industries = ["制造业", "物流", "科技", "零售"]
    regions = ["上海松江", "上海浦东"]
    rows = []
    for index in range(60):
        region = regions[index % len(regions)]
        office_count = index % 4 + 1
        rows.append({"company_name": f"合成企业{index + 1:03d}", "industry": industries[index % len(industries)], "region": region, "employee_count": 30 + index * 5, "member_count": 5 + index * 3, "office_count": office_count, "branch_count": max(0, office_count - 1), "locations": [region], "company_scale": "LARGE" if index >= 40 else "MEDIUM" if index >= 15 else "SMALL", "company_status": "ACTIVE", "existing_products": [], "contact_availability": index % 3 != 0, "cross_region_presence": office_count >= 3})
    return rows


def main() -> None:
    _write_jsonl(Path("evals/rules/dataset.jsonl"), rule_eval_rows())
    _write_jsonl(Path("data/synthetic_customers/customers.jsonl"), synthetic_customers())


if __name__ == "__main__":
    main()

