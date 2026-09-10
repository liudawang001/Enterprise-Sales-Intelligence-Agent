from datetime import UTC, datetime

from app.evidence.models import Evidence, FieldVerificationPolicy

SOURCE_BASE = {
    "OFFICIAL_WEBSITE": 0.88,
    "ENTERPRISE_DATABASE": 0.9,
    "MAP_POI": 0.75,
    "INTERNAL_DATABASE": 0.82,
    "PUBLIC_WEBPAGE": 0.58,
    "WEB_SEARCH": 0.5,
}


def calculate_evidence_confidence(
    evidence: Evidence,
    policy: FieldVerificationPolicy,
    *,
    agreement_count: int = 1,
    now: datetime | None = None,
) -> tuple[float, bool]:
    now = now or datetime.now(UTC)
    retrieved = evidence.retrieved_at
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=UTC)
    stale = bool(policy.max_age_days and (now - retrieved).days > policy.max_age_days)
    base = SOURCE_BASE[evidence.source_type.value]
    direct_bonus = 0.04 if evidence.extraction_method in {"STRUCTURED", "DIRECT"} else 0
    agreement_bonus = min(0.12, max(0, agreement_count - 1) * 0.06)
    stale_penalty = 0.25 if stale else 0
    return round(max(0, min(1, base + direct_bonus + agreement_bonus - stale_penalty)), 4), stale
