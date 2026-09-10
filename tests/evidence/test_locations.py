from app.entities.enums import EntityType
from app.entities.models import (
    CanonicalEnterprise,
    EnterpriseCandidateLink,
    EnterpriseLocation,
)
from app.evidence.locations import deduplicate_office_locations
from app.evidence.service import EvidenceVerificationService
from app.repositories.enterprise_repository import InMemoryEnterpriseRepository
from app.repositories.evidence_repository import InMemoryEvidenceRepository
from app.research.models import RawEnterpriseCandidate, SourceRecord
from app.research.repository import InMemoryResearchRepository


def location(address: str, *, kind=EntityType.OFFICE, lat=None, lng=None):
    return EnterpriseLocation(
        enterprise_id="enterprise",
        location_type=kind,
        address=address,
        normalized_address=address,
        lat=lat,
        lng=lng,
    )


def test_office_count_uses_deduplicated_acceptable_locations():
    values = [
        location("上海市A路1号"),
        location("上海市 A路1号"),
        location("上海市B路2号", kind=EntityType.BRANCH),
        location("上海市C路3号", kind=EntityType.STORE),
    ]
    assert len(deduplicate_office_locations(values)) == 2


def test_nearby_coordinates_are_deduplicated():
    values = [
        location("地址A", lat=31.0, lng=121.0),
        location("地址A附楼", lat=31.0001, lng=121.0001),
    ]
    assert len(deduplicate_office_locations(values)) == 1


def test_map_pois_become_deduplicated_location_and_office_count_evidence():
    research = InMemoryResearchRepository()
    candidate = research.save_candidate(
        RawEnterpriseCandidate(
            research_run_id="research-run",
            source_provider="map",
            source_name="ABC公司",
            normalized_name="abc公司",
        )
    )
    for index, address in enumerate(("A路1号", "A路1号", "B路2号")):
        research.save_source(
            SourceRecord(
                research_run_id="research-run",
                candidate_id=candidate.candidate_id,
                provider="map",
                source_type="MAP_POI",
                source_id=f"poi-{index}",
                payload_json={"address": address},
            )
        )
    enterprises = InMemoryEnterpriseRepository(research)
    enterprise = enterprises.save_enterprise(
        CanonicalEnterprise(
            canonical_name="ABC公司", source_candidate_ids=[candidate.candidate_id]
        )
    )
    enterprises.save_candidate_link(
        EnterpriseCandidateLink(
            enterprise_id=enterprise.enterprise_id,
            candidate_id=candidate.candidate_id,
            resolution_run_id="resolution-run",
            confidence=1,
        )
    )
    evidence = InMemoryEvidenceRepository()
    service = EvidenceVerificationService(evidence, enterprises)
    run = service.start_run(
        task_id="task",
        candidate_set_id="candidate-set",
        resolution_run_id="resolution-run",
    )
    service.collect_evidence(run)
    assert len(enterprises.locations) == 2
    counts = evidence.list_evidence(enterprise.enterprise_id, "office_count")
    assert len(counts) == 1 and counts[0].value == 2
