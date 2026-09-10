from app.evidence.enums import EvidenceSourceType
from app.evidence.models import FieldVerificationPolicy

DEFAULT_POLICIES = {
    "legal_name": FieldVerificationPolicy(
        field_name="legal_name",
        source_priorities=[EvidenceSourceType.ENTERPRISE_DATABASE, EvidenceSourceType.OFFICIAL_WEBSITE, EvidenceSourceType.MAP_POI],
        min_sources_for_verified=1,
        min_confidence=0.75,
        max_age_days=3650,
    ),
    "unified_social_credit_code": FieldVerificationPolicy(
        field_name="unified_social_credit_code",
        source_priorities=[EvidenceSourceType.ENTERPRISE_DATABASE],
        min_sources_for_verified=1,
        min_confidence=0.8,
        max_age_days=3650,
    ),
    "website": FieldVerificationPolicy(
        field_name="website",
        source_priorities=[EvidenceSourceType.OFFICIAL_WEBSITE, EvidenceSourceType.ENTERPRISE_DATABASE, EvidenceSourceType.WEB_SEARCH, EvidenceSourceType.MAP_POI],
        min_sources_for_verified=1,
        min_confidence=0.72,
        max_age_days=365,
    ),
    "public_phone": FieldVerificationPolicy(
        field_name="public_phone",
        source_priorities=[EvidenceSourceType.OFFICIAL_WEBSITE, EvidenceSourceType.ENTERPRISE_DATABASE, EvidenceSourceType.MAP_POI, EvidenceSourceType.PUBLIC_WEBPAGE],
        min_sources_for_verified=2,
        min_confidence=0.72,
        max_age_days=365,
    ),
    "address": FieldVerificationPolicy(
        field_name="address",
        source_priorities=[EvidenceSourceType.ENTERPRISE_DATABASE, EvidenceSourceType.OFFICIAL_WEBSITE, EvidenceSourceType.MAP_POI],
        min_sources_for_verified=2,
        min_confidence=0.72,
        max_age_days=730,
    ),
    "office_count": FieldVerificationPolicy(
        field_name="office_count",
        source_priorities=[EvidenceSourceType.MAP_POI, EvidenceSourceType.OFFICIAL_WEBSITE, EvidenceSourceType.ENTERPRISE_DATABASE],
        min_sources_for_verified=2,
        min_confidence=0.7,
        max_age_days=365,
    ),
    "office_location": FieldVerificationPolicy(
        field_name="office_location",
        source_priorities=[EvidenceSourceType.MAP_POI, EvidenceSourceType.OFFICIAL_WEBSITE],
        min_sources_for_verified=1,
        min_confidence=0.7,
        max_age_days=365,
    ),
}


def policy_for(field_name: str) -> FieldVerificationPolicy:
    return DEFAULT_POLICIES.get(
        field_name,
        FieldVerificationPolicy(
            field_name=field_name,
            source_priorities=list(EvidenceSourceType),
            min_sources_for_verified=2,
        ),
    )
