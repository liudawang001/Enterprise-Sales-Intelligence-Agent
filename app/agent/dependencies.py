from dataclasses import dataclass

from app.config import get_settings
from app.entities.service import EntityResolutionService
from app.evidence.models import VerificationBudget
from app.evidence.service import EvidenceVerificationService
from app.evidence.targeted import TargetedVerificationService, VerificationBudgetGuard
from app.repositories.enterprise_repository import InMemoryEnterpriseRepository
from app.repositories.evidence_repository import InMemoryEvidenceRepository
from app.repositories.lead_score_repository import InMemoryLeadScoreRepository
from app.repositories.mock_task_repository import MockTaskRepository
from app.rules.service import BusinessRuleService
from app.scoring.profiles import demo_scoring_profiles
from app.services.business_service import MockBusinessService
from app.services.research_service import ResearchService
from app.services.scoring_service import LeadScoringService, MockScoringService
from app.services.task_service import TaskService


@dataclass
class AgentDependencies:
    task_repository: MockTaskRepository
    task_service: TaskService
    business_service: MockBusinessService
    research_service: ResearchService
    scoring_service: MockScoringService
    rule_service: BusinessRuleService
    knowledge_service: object | None = None
    enterprise_repository: InMemoryEnterpriseRepository | None = None
    evidence_repository: InMemoryEvidenceRepository | None = None
    lead_score_repository: InMemoryLeadScoreRepository | None = None
    entity_resolution_service: EntityResolutionService | None = None
    verification_service: EvidenceVerificationService | None = None
    lead_scoring_service: LeadScoringService | None = None
    targeted_verification_service: TargetedVerificationService | None = None


def build_dependencies() -> AgentDependencies:
    settings = get_settings()
    repository = MockTaskRepository()
    rule_service = BusinessRuleService()
    rule_service.seed_demo_rules()
    research_service = ResearchService()
    enterprise_repository = InMemoryEnterpriseRepository(research_service.repository)
    evidence_repository = InMemoryEvidenceRepository()
    lead_score_repository = InMemoryLeadScoreRepository()
    for profile in demo_scoring_profiles():
        lead_score_repository.save_profile(profile)
    verification_service = EvidenceVerificationService(
        evidence_repository, enterprise_repository
    )
    verification_budget = VerificationBudget(
        max_extra_tool_calls=settings.verification_max_extra_calls,
        max_calls_per_entity=settings.verification_max_calls_per_entity,
        max_rounds=settings.verification_max_rounds,
    )

    async def targeted_provider(enterprise_id: str, fields: list[str]):
        link = next(
            (
                value
                for value in enterprise_repository.candidate_links.values()
                if value.enterprise_id == enterprise_id
            ),
            None,
        )
        if not link:
            return []
        candidate = research_service.repository.get_candidate(link.candidate_id)
        if not candidate:
            return []
        sources = await research_service.targeted_enrich_fields(
            candidate.research_run_id, candidate.candidate_id, fields
        )
        result = []
        for source in sources:
            for evidence in verification_service.extractor.extract(
                enterprise_id, source, candidate
            ):
                evidence.normalized_value = verification_service.normalizer.normalize(
                    evidence.field_name, evidence.value
                )
                result.append(evidence)
        return result
    return AgentDependencies(
        task_repository=repository,
        task_service=TaskService(repository),
        business_service=MockBusinessService(rule_service),
        research_service=research_service,
        scoring_service=MockScoringService(),
        rule_service=rule_service,
        enterprise_repository=enterprise_repository,
        evidence_repository=evidence_repository,
        lead_score_repository=lead_score_repository,
        entity_resolution_service=EntityResolutionService(enterprise_repository),
        verification_service=verification_service,
        lead_scoring_service=LeadScoringService(lead_score_repository, evidence_repository, enterprise_repository, rule_service.repository),
        targeted_verification_service=TargetedVerificationService(
            evidence_repository,
            targeted_provider,
            VerificationBudgetGuard(verification_budget),
        ),
    )
