from __future__ import annotations

import json
from datetime import UTC, datetime

from app.criteria.models import LeadCriteria
from app.evidence.enums import EvidenceSourceType
from app.evidence.models import Evidence, ResolvedField, VerifiedEnterpriseProfile
from app.evidence.normalizer import EvidenceNormalizer
from app.evidence.resolver import ConflictAwareFieldResolver
from app.scoring.engine import DeterministicScoringEngine
from app.scoring.enums import LeadRankStatus
from app.scoring.profiles import demo_scoring_profiles


def _evidence(index: int, value: str, source_type: EvidenceSourceType) -> Evidence:
    return Evidence(
        evidence_id=f"evidence-{index}-{source_type.value}",
        enterprise_id="enterprise",
        field_name="public_phone",
        value=value,
        normalized_value=EvidenceNormalizer().normalize("public_phone", value),
        provider=source_type.value.lower(),
        source_type=source_type,
        source_record_id=f"source-{index}-{source_type.value}",
        retrieved_at=datetime.now(UTC),
        extraction_method="STRUCTURED",
    )


def evaluate_evidence() -> dict[str, float | int]:
    resolver = ConflictAwareFieldResolver()
    conflict_correct = primary_correct = traceable = 0
    for index in range(30):
        conflict = index % 2 == 1
        official = f"021-{1000 + index}"
        secondary = f"021-{2000 + index}" if conflict else official
        evidence = [
            _evidence(index, official, EvidenceSourceType.OFFICIAL_WEBSITE),
            _evidence(index, secondary, EvidenceSourceType.MAP_POI),
        ]
        source_records = {item.source_record_id for item in evidence}
        evidence_by_id = {item.evidence_id: item for item in evidence}
        result = resolver.resolve("enterprise", "public_phone", evidence)
        conflict_correct += (result.status == "CONFLICTING") == conflict
        primary_correct += result.primary_value == official
        ids = set(result.supporting_evidence_ids) | set(result.conflicting_evidence_ids)
        traceable += len(ids) == 2 and all(
            evidence_by_id[evidence_id].source_record_id in source_records
            for evidence_id in ids
        )
    return {
        "cases": 30,
        "conflict_detection_accuracy": conflict_correct / 30,
        "primary_value_selection_accuracy": primary_correct / 30,
        "source_traceability": traceable / 30,
    }


def _field(name: str, value, index: int) -> ResolvedField:
    return ResolvedField(enterprise_id=f"enterprise-{index}", field_name=name, primary_value=value, status="VERIFIED", confidence=0.9, supporting_evidence_ids=[f"evidence-{index}-{name}"])


def _profile(index: int, office_count: int, *, legal_name: bool = True) -> VerifiedEnterpriseProfile:
    fields = {
        "company_status": _field("company_status", "正常", index),
        "office_count": _field("office_count", office_count, index),
        "cross_region_presence": _field("cross_region_presence", True, index),
        "company_scale": _field("company_scale", "LARGE", index),
        "employee_count": _field("employee_count", 200, index),
        "address": _field("address", "上海松江区A路1号", index),
        "public_phone": _field("public_phone", "021-55550000", index),
        "website": _field("website", "example.com", index),
    }
    if legal_name:
        fields["legal_name"] = _field("legal_name", f"企业{index}", index)
    return VerifiedEnterpriseProfile(verification_run_id="verification", enterprise_id=f"enterprise-{index}", fields=fields, status="VERIFIED", evidence_coverage=1, required_fields=list(fields))


def evaluate_scoring() -> dict[str, float | int]:
    engine = DeterministicScoringEngine()
    scoring_profile = demo_scoring_profiles()[0]
    criteria = LeadCriteria(criteria_id="criteria", task_id="task", task_version=1, business_code="GROUP_VNET", region_scope=["上海松江"], target_count=30)
    deterministic = monotonic = 0
    for index in range(30):
        low = engine.score(task_id="task", profile=_profile(index, index % 4 + 1), criteria=criteria, scoring_profile=scoring_profile)
        repeated = engine.score(task_id="task", profile=_profile(index, index % 4 + 1), criteria=criteria, scoring_profile=scoring_profile)
        high = engine.score(task_id="task", profile=_profile(index, index % 4 + 2), criteria=criteria, scoring_profile=scoring_profile)
        deterministic += low.total_score == repeated.total_score
        low_office = next(item for item in low.component_scores if item.component == "office_distribution")
        high_office = next(item for item in high.component_scores if item.component == "office_distribution")
        monotonic += high_office.weighted_score >= low_office.weighted_score
    missing = engine.score(task_id="task", profile=_profile(999, 1, legal_name=False), criteria=criteria, scoring_profile=scoring_profile)
    return {
        "cases": 30,
        "determinism": deterministic / 30,
        "monotonicity": monotonic / 30,
        "profile_reproducibility": deterministic / 30,
        "hard_required_missing_not_scorable": float(missing.rank_status == LeadRankStatus.NOT_SCORABLE and missing.total_score is None),
    }


def evaluate() -> dict:
    return {"evidence": evaluate_evidence(), "scoring": evaluate_scoring()}


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
