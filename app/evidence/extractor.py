from __future__ import annotations

from typing import ClassVar

from app.evidence.enums import EvidenceSourceType
from app.evidence.models import Evidence
from app.research.models import RawEnterpriseCandidate, ResearchSourceType, SourceRecord
from app.research.safety import filter_public_contacts

SOURCE_TYPE_MAP = {
    ResearchSourceType.OFFICIAL_WEBSITE: EvidenceSourceType.OFFICIAL_WEBSITE,
    ResearchSourceType.ENTERPRISE_DATABASE: EvidenceSourceType.ENTERPRISE_DATABASE,
    ResearchSourceType.MAP_POI: EvidenceSourceType.MAP_POI,
    ResearchSourceType.WEB_SEARCH: EvidenceSourceType.WEB_SEARCH,
    ResearchSourceType.WEBSITE_CANDIDATE: EvidenceSourceType.WEB_SEARCH,
    ResearchSourceType.PUBLIC_WEBPAGE: EvidenceSourceType.PUBLIC_WEBPAGE,
}


class SourceRecordEvidenceExtractor:
    FIELD_ALIASES: ClassVar[dict[str, str]] = {
        "name": "legal_name",
        "company_name": "legal_name",
        "source_name": "legal_name",
        "credit_code": "unified_social_credit_code",
        "website_candidate": "website",
        "phone": "public_phone",
        "company_scale": "company_scale",
        "basic_scale": "company_scale",
    }
    FIELDS: ClassVar[set[str]] = {
        "legal_name",
        "unified_social_credit_code",
        "industry",
        "company_scale",
        "website",
        "public_phone",
        "address",
        "office_count",
        "branch_count",
        "employee_count",
        "member_count",
        "cross_region_presence",
        "office_location",
    }

    def extract(
        self,
        enterprise_id: str,
        source: SourceRecord,
        candidate: RawEnterpriseCandidate,
    ) -> list[Evidence]:
        payload = dict(source.payload_json or {})
        values: dict[str, object] = {}
        for key, value in payload.items():
            field = self.FIELD_ALIASES.get(key, key)
            if source.source_type == ResearchSourceType.MAP_POI and field == "address":
                field = "office_location"
            if field in self.FIELDS and value is not None and value != "" and value != []:
                values[field] = value
        if source.source_type == ResearchSourceType.ENTERPRISE_DATABASE and "legal_name" not in values:
            values["legal_name"] = candidate.source_name
            for field in self.FIELDS - {"legal_name"}:
                candidate_value = getattr(candidate, field, None)
                if candidate_value is not None and candidate_value != "" and candidate_value != []:
                    values.setdefault(field, candidate_value)
        if source.source_type in {
            ResearchSourceType.OFFICIAL_WEBSITE,
            ResearchSourceType.PUBLIC_WEBPAGE,
        }:
            values.setdefault("website", source.source_url or candidate.website_candidate)
            phones, _ = filter_public_contacts(source.content_text or "")
            if phones:
                values.setdefault("public_phone", phones[0])
        phone = values.get("public_phone")
        if phone:
            public_phones, _ = filter_public_contacts(str(phone))
            if not public_phones:
                values.pop("public_phone", None)
            else:
                values["public_phone"] = public_phones[0]
        source_type = SOURCE_TYPE_MAP.get(source.source_type, EvidenceSourceType.PUBLIC_WEBPAGE)
        return [
            Evidence(
                enterprise_id=enterprise_id,
                field_name=field,
                value=value,
                provider=source.provider,
                source_type=source_type,
                source_record_id=source.source_record_id,
                source_url=source.source_url,
                retrieved_at=source.retrieved_at,
                extraction_method="STRUCTURED" if field in payload or not source.content_text else "REGEX",
                raw_reference=(source.content_text or "")[:500] or None,
            )
            for field, value in values.items()
        ]
