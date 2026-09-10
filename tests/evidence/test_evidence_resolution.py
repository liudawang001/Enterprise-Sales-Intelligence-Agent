from datetime import UTC, datetime, timedelta

import pytest

from app.evidence.coverage import evidence_coverage
from app.evidence.enums import EvidenceSourceType, FieldVerificationStatus
from app.evidence.extractor import SourceRecordEvidenceExtractor
from app.evidence.models import (
    Evidence,
    ResolvedField,
    VerificationBudget,
    VerifiedEnterpriseProfile,
)
from app.evidence.normalizer import EvidenceNormalizer
from app.evidence.resolver import ConflictAwareFieldResolver
from app.evidence.targeted import TargetedVerificationService, VerificationBudgetGuard
from app.repositories.evidence_repository import InMemoryEvidenceRepository
from app.research.models import RawEnterpriseCandidate, SourceRecord


def evidence(value, source_type, *, field="public_phone", days_old=0):
    return Evidence(
        enterprise_id="enterprise",
        field_name=field,
        value=value,
        normalized_value=EvidenceNormalizer().normalize(field, value),
        provider=source_type.value.lower(),
        source_type=source_type,
        source_record_id=f"source-{source_type}-{value}",
        retrieved_at=datetime.now(UTC) - timedelta(days=days_old),
        extraction_method="STRUCTURED",
    )


def test_multi_source_agreement_normalizes_formats_and_verifies():
    result = ConflictAwareFieldResolver().resolve(
        "enterprise",
        "public_phone",
        [
            evidence("021-1234-5678", EvidenceSourceType.OFFICIAL_WEBSITE),
            evidence("021 1234 5678", EvidenceSourceType.ENTERPRISE_DATABASE),
        ],
    )
    assert result.status == FieldVerificationStatus.VERIFIED
    assert len(result.supporting_evidence_ids) == 2


def test_conflict_is_preserved_while_policy_selects_primary():
    result = ConflictAwareFieldResolver().resolve(
        "enterprise",
        "public_phone",
        [
            evidence("021-1111", EvidenceSourceType.OFFICIAL_WEBSITE),
            evidence("021-2222", EvidenceSourceType.MAP_POI),
        ],
    )
    assert result.status == FieldVerificationStatus.CONFLICTING
    assert result.primary_value == "021-1111"
    assert result.alternatives == ["021-2222"]
    assert result.conflicting_evidence_ids


def test_stale_evidence_lowers_confidence_without_deleting_it():
    fresh = ConflictAwareFieldResolver().resolve(
        "enterprise", "website", [evidence("https://example.com", EvidenceSourceType.OFFICIAL_WEBSITE, field="website")]
    )
    stale = ConflictAwareFieldResolver().resolve(
        "enterprise", "website", [evidence("https://example.com", EvidenceSourceType.OFFICIAL_WEBSITE, field="website", days_old=500)]
    )
    assert stale.confidence < fresh.confidence
    assert stale.supporting_evidence_ids


def test_task_aware_coverage_counts_traceable_fields():
    fields = {
        "website": ResolvedField(enterprise_id="e", field_name="website", primary_value="example.com", status="VERIFIED", confidence=0.9),
        "public_phone": ResolvedField(enterprise_id="e", field_name="public_phone", status="MISSING", confidence=0),
    }
    assert evidence_coverage(fields, ["website", "public_phone"]) == 0.5


@pytest.mark.asyncio
async def test_targeted_verification_only_requests_missing_field_and_is_bounded():
    repository = InMemoryEvidenceRepository()
    profile = VerifiedEnterpriseProfile(
        verification_run_id="run",
        enterprise_id="enterprise",
        fields={},
        status="UNVERIFIED",
        evidence_coverage=0,
        required_fields=["website"],
    )
    calls = []

    def provider(enterprise_id, fields):
        calls.append((enterprise_id, fields))
        return [evidence("example.com", EvidenceSourceType.OFFICIAL_WEBSITE, field="website")]

    guard = VerificationBudgetGuard(VerificationBudget(max_extra_tool_calls=1, max_calls_per_entity=1))
    service = TargetedVerificationService(repository, provider, guard)
    assert guard.start_round()
    assert len(await service.enrich(profile, ["website"])) == 1
    assert await service.enrich(profile, ["website"]) == []
    assert calls == [("enterprise", ["website"])]


def test_evidence_extraction_filters_personal_mobile_number():
    candidate = RawEnterpriseCandidate(
        research_run_id="run",
        source_provider="fixture",
        source_name="ABC公司",
        normalized_name="abc公司",
    )
    source = SourceRecord(
        research_run_id="run",
        candidate_id=candidate.candidate_id,
        provider="fixture",
        source_type="ENTERPRISE_DATABASE",
        payload_json={"public_phone": "13800138000"},
    )
    values = SourceRecordEvidenceExtractor().extract("enterprise", source, candidate)
    assert not any(item.field_name == "public_phone" for item in values)
