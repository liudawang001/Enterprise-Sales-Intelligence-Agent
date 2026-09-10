from app.agent.dependencies import AgentDependencies
from app.agent.enums import TaskStage, TaskStatus
from app.agent.state import AgentState


def score_leads(state: AgentState, deps: AgentDependencies) -> dict:
    task = deps.task_repository.get_task(state.get("active_task_id"))
    if not task or not deps.lead_scoring_service:
        raise ValueError("LEAD_SCORING_FAILED")
    lead_set, scored = deps.lead_scoring_service.score_task(task_id=task.task_id, criteria_id=state["criteria_snapshot_id"], profile_ids=state.get("verified_profile_ids", []), target_count=task.target_count or 0, task_version=task.version)
    if task:
        deps.task_repository.set_status(task.task_id, stage=TaskStage.SCORING, status=TaskStatus.RUNNING)
    return {
        "lead_results": scored,
        "lead_set_id": lead_set.lead_set_id,
        "verified_set_id": lead_set.lead_set_id,
        "scoring_profile_id": lead_set.scoring_profile_id,
        "task_stage": TaskStage.SCORING.value,
    }
