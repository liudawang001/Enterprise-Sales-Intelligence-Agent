from app.entities.enums import EntityRelationType
from app.entities.service import EntityResolutionService
from app.repositories.enterprise_repository import InMemoryEnterpriseRepository
from app.research.models import CandidateSet, RawEnterpriseCandidate
from app.research.repository import InMemoryResearchRepository


def test_resolution_service_merges_same_but_persists_branch_as_relation():
    research = InMemoryResearchRepository()
    candidates = [
        RawEnterpriseCandidate(
            research_run_id="run",
            source_provider="provider-a",
            source_name="ABC科技有限公司",
            normalized_name="abc科技有限公司",
            unified_social_credit_code="CREDIT-A",
        ),
        RawEnterpriseCandidate(
            research_run_id="run",
            source_provider="provider-b",
            source_name="ABC科技股份有限公司",
            normalized_name="abc科技股份有限公司",
            unified_social_credit_code="CREDIT-A",
        ),
        RawEnterpriseCandidate(
            research_run_id="run",
            source_provider="provider-c",
            source_name="ABC科技有限公司上海分公司",
            normalized_name="abc科技有限公司上海分公司",
        ),
    ]
    for item in candidates:
        research.save_candidate(item)
    candidate_set = research.save_candidate_set(
        CandidateSet(
            research_run_id="run",
            stage="RESEARCHED",
            criteria_snapshot_id="criteria",
            search_plan_id="plan",
            candidate_ids=[item.candidate_id for item in candidates],
        )
    )
    repository = InMemoryEnterpriseRepository(research)
    run = EntityResolutionService(repository).resolve(
        task_id="task", candidate_set_id=candidate_set.candidate_set_id
    )
    assert run.enterprise_count == 2
    assert len(repository.candidate_links) == 3
    assert any(
        item.relation_type == EntityRelationType.BRANCH_OF
        for item in repository.relations.values()
    )
