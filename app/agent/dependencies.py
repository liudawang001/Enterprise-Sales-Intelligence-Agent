from dataclasses import dataclass

from app.repositories.mock_task_repository import MockTaskRepository
from app.services.business_service import MockBusinessService
from app.services.research_service import MockResearchService
from app.services.scoring_service import MockScoringService
from app.services.task_service import TaskService
from app.rules.service import BusinessRuleService


@dataclass
class AgentDependencies:
    task_repository: MockTaskRepository
    task_service: TaskService
    business_service: MockBusinessService
    research_service: MockResearchService
    scoring_service: MockScoringService
    rule_service: BusinessRuleService
    knowledge_service: object | None = None


def build_dependencies() -> AgentDependencies:
    repository = MockTaskRepository()
    rule_service = BusinessRuleService()
    rule_service.seed_demo_rules()
    return AgentDependencies(
        task_repository=repository,
        task_service=TaskService(repository),
        business_service=MockBusinessService(rule_service),
        research_service=MockResearchService(),
        scoring_service=MockScoringService(),
        rule_service=rule_service,
    )
