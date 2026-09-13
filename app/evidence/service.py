from __future__ import annotations

from datetime import UTC, datetime

from app.entities.enums import EntityType
from app.entities.models import EnterpriseLocation
from app.evidence.coverage import enterprise_status, evidence_coverage
from app.evidence.extractor import SourceRecordEvidenceExtractor
from app.evidence.locations import deduplicate_office_locations
from app.evidence.models import (
    Evidence,
    ResolvedField,
    VerificationBudget,
    VerificationRun,
    VerifiedEnterpriseProfile,
)
from app.evidence.normalizer import EvidenceNormalizer
from app.evidence.resolver import ConflictAwareFieldResolver


class EvidenceVerificationService:
    def __init__(self, repository, enterprise_repository) -> None:
        self.repository = repository
        self.enterprise_repository = enterprise_repository
        self.extractor = SourceRecordEvidenceExtractor()
        self.normalizer = EvidenceNormalizer()
        self.resolver = ConflictAwareFieldResolver()

    def start_run(
        self, *, task_id: str, candidate_set_id: str, resolution_run_id: str, budget: VerificationBudget | None = None
    ) -> VerificationRun:
        return self.repository.save_run(
            VerificationRun(
                task_id=task_id,
                researched_candidate_set_id=candidate_set_id,
                resolution_run_id=resolution_run_id,
                budget=budget or VerificationBudget(),
            )
        )

    def collect_evidence(self, run: VerificationRun) -> list[Evidence]:
        collected = []
        for link in self.enterprise_repository.candidate_links.values():
            if link.resolution_run_id != run.resolution_run_id:
                continue
            candidate = self.enterprise_repository.research_repository.get_candidate(link.candidate_id)
            if not candidate:
                continue
            for source in self.enterprise_repository.research_repository.get_sources(link.candidate_id):
                for item in self.extractor.extract(link.enterprise_id, source, candidate):
                    item.normalized_value = self.normalizer.normalize(item.field_name, item.value)
                    saved = self.repository.save_evidence(item)
                    collected.append(saved)
                    if item.field_name == "office_location":
                        lat = lng = None
                        location = (source.payload_json or {}).get("location")
                        if isinstance(location, str) and "," in location:
                            try:
                                lng, lat = (float(value) for value in location.split(",", 1))
                            except ValueError:
                                lat = lng = None
                        self.enterprise_repository.save_location(
                            EnterpriseLocation(
                                enterprise_id=link.enterprise_id,
                                location_type=EntityType.OFFICE,
                                address=str(item.value),
                                normalized_address=str(item.normalized_value),
                                lat=lat,
                                lng=lng,
                                evidence_ids=[saved.evidence_id],
                                verification_status="PARTIAL",
                            )
                        )
        for enterprise_id in {
            link.enterprise_id
            for link in self.enterprise_repository.candidate_links.values()
            if link.resolution_run_id == run.resolution_run_id
        }:
            locations = deduplicate_office_locations(
                [item for item in self.enterprise_repository.locations.values() if item.enterprise_id == enterprise_id]
            )
            if locations:
                source_evidence_id = locations[0].evidence_ids[0]
                source_evidence = self.repository.evidence[source_evidence_id]
                collected.append(
                    self.repository.save_evidence(
                        Evidence(
                            enterprise_id=enterprise_id,
                            field_name="office_count",
                            value=len(locations),
                            normalized_value=len(locations),
                            provider="location_deduplicator",
                            source_type=source_evidence.source_type,
                            source_record_id=source_evidence.source_record_id,
                            source_url=source_evidence.source_url,
                            retrieved_at=source_evidence.retrieved_at,
                            extraction_method="DETERMINISTIC_AGGREGATION",
                            raw_reference=",".join(
                                evidence_id for location in locations for evidence_id in location.evidence_ids
                            ),
                        )
                    )
                )
        return collected

    def resolve_fields(
        self,
        enterprise_id: str,
        required_fields: list[str],
        *,
        verification_run_id: str | None = None,
    ) -> dict:
        evidence = self.repository.list_evidence(enterprise_id)
        names = set(required_fields) | {item.field_name for item in evidence if item.field_name != "office_location"}
        fields = {}
        for name in sorted(names):
            field_evidence = [item for item in evidence if item.field_name == name]
            resolved = self.resolver.resolve(enterprise_id, name, field_evidence)
            for item in field_evidence:
                self.repository.save_evidence(item)
            fields[name] = self.repository.save_resolved_field(resolved, verification_run_id=verification_run_id)
        return fields

    def build_profile(
        self, run: VerificationRun, enterprise_id: str, required_fields: list[str]
    ) -> VerifiedEnterpriseProfile:
        fields = self.resolve_fields(
            enterprise_id,
            required_fields,
            verification_run_id=run.verification_run_id,
        )
        addresses = [field for name, field in fields.items() if name == "address"]
        addresses.extend(
            ResolvedField(
                enterprise_id=enterprise_id,
                field_name="office_location",
                primary_value=item.value,
                status="PARTIAL",
                confidence=item.confidence,
                supporting_evidence_ids=[item.evidence_id],
            )
            for item in self.repository.list_evidence(enterprise_id, "office_location")
        )
        profile = VerifiedEnterpriseProfile(
            verification_run_id=run.verification_run_id,
            enterprise_id=enterprise_id,
            fields=fields,
            addresses=addresses,
            status=enterprise_status(fields),
            evidence_coverage=evidence_coverage(fields, required_fields),
            required_fields=required_fields,
        )
        return self.repository.save_profile(profile)

    def finish_run(
        self, run: VerificationRun, profiles: list[VerifiedEnterpriseProfile], warnings: list[str] | None = None
    ) -> VerificationRun:
        return self.repository.save_run(
            run.model_copy(
                update={
                    "status": "COMPLETED",
                    "profile_ids": [item.profile_id for item in profiles],
                    "warnings": warnings or [],
                    "finished_at": datetime.now(UTC),
                }
            )
        )

    def fields_needing_enrichment(self, profile: VerifiedEnterpriseProfile) -> list[str]:
        return [
            name
            for name in profile.required_fields
            if not profile.field(name) or profile.field(name).status in {"MISSING", "UNVERIFIED"}
        ]
