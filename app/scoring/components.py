from __future__ import annotations

from typing import Any

from app.criteria.evaluator import DefaultCriteriaEvaluator
from app.criteria.models import LeadCriteria
from app.evidence.enums import FieldVerificationStatus
from app.evidence.models import VerifiedEnterpriseProfile
from app.scoring.models import ScoreComponentConfig


def profile_values(profile: VerifiedEnterpriseProfile) -> dict[str, Any]:
    return {name: field.primary_value for name, field in profile.fields.items()}


def evidence_ids(profile: VerifiedEnterpriseProfile, fields: list[str]) -> list[str]:
    return sorted(
        {
            item
            for name in fields
            if (field := profile.field(name))
            for item in field.supporting_evidence_ids + field.conflicting_evidence_ids
        }
    )


def is_missing(profile: VerifiedEnterpriseProfile, fields: list[str]) -> bool:
    return bool(fields) and all(not profile.field(name) or profile.field(name).status in {FieldVerificationStatus.MISSING, FieldVerificationStatus.UNVERIFIED} for name in fields)


def calculate_component(config: ScoreComponentConfig, profile: VerifiedEnterpriseProfile, criteria: LeadCriteria) -> tuple[float, list[str]]:
    values = profile_values(profile)
    name = config.component
    if name == "business_fit":
        outcome = DefaultCriteriaEvaluator().evaluate_hard_constraints(values, criteria)
        return ({"MATCH": 1.0, "UNKNOWN": 0.5, "NO_MATCH": 0.0}[outcome.value], [f"BUSINESS_FIT_{outcome.value}"])
    if name == "office_distribution":
        count = float(values.get("office_count") or 0)
        target = float(config.config.get("target", 3))
        raw = min(1, count / max(1, target))
        if values.get("cross_region_presence"):
            raw = min(1, raw + 0.2)
        return raw, ["OFFICE_DISTRIBUTION"]
    if name == "company_scale":
        scale = str(values.get("company_scale") or "").upper()
        employees = float(values.get("employee_count") or 0)
        raw = 1 if scale in {"LARGE", "MEDIUM", "中型", "大型"} or employees >= 100 else 0.4 if employees > 0 else 0
        return raw, ["COMPANY_SCALE"]
    if name == "industry_preference":
        industry = values.get("industry")
        preferences = [item for item in criteria.soft_constraints if item.field == "industry"]
        if not preferences:
            return 0, ["NO_INDUSTRY_PREFERENCE"]
        matches = any(industry == item.value or isinstance(item.value, list) and industry in item.value for item in preferences)
        return (1 if matches else 0), ["INDUSTRY_PREFERRED" if matches else "INDUSTRY_NOT_PREFERRED"]
    if name == "location_fit":
        address = str(values.get("address") or "").replace("市", "").replace("区", "")
        match = any(region.replace("市", "").replace("区", "") in address for region in criteria.region_scope)
        return (1 if match else 0), ["LOCATION_MATCH" if match else "LOCATION_MISMATCH"]
    if name == "evidence_confidence":
        fields = list(profile.fields.values())
        average = sum(item.confidence for item in fields) / len(fields) if fields else 0
        conflict_rate = sum(item.status == FieldVerificationStatus.CONFLICTING for item in fields) / len(fields) if fields else 0
        return max(0, min(1, 0.6 * profile.evidence_coverage + 0.4 * average - 0.3 * conflict_rate)), ["EVIDENCE_QUALITY"]
    if name == "contact_completeness":
        quality = {FieldVerificationStatus.VERIFIED: 1, FieldVerificationStatus.PARTIAL: 0.7, FieldVerificationStatus.CONFLICTING: 0.3, FieldVerificationStatus.UNVERIFIED: 0.2, FieldVerificationStatus.MISSING: 0}
        return sum(quality.get(profile.field(field).status, 0) if profile.field(field) else 0 for field in ("public_phone", "website", "address")) / 3, ["CONTACT_COMPLETENESS"]
    return 0, ["UNKNOWN_COMPONENT"]
