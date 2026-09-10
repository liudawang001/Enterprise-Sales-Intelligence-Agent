from app.agent.dependencies import AgentDependencies
from app.agent.enums import TaskStage, TaskStatus
from app.agent.state import AgentState


def score_leads(state: AgentState, deps: AgentDependencies) -> dict:
    leads = deps.research_service.get_candidates(state.get("candidate_set_id"))
    task = deps.task_repository.get_task(state.get("active_task_id"))
    scored = deps.scoring_service.score(leads, region=task.region if task else None)
    if task:
        deps.task_repository.set_status(task.task_id, stage=TaskStage.SCORING, status=TaskStatus.RUNNING)
    return {
        "lead_results": [lead.model_dump() for lead in scored],
        "task_stage": TaskStage.SCORING.value,
    }
