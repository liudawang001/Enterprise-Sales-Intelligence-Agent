from app.agent.dependencies import AgentDependencies
from app.agent.enums import TaskStage
from app.agent.state import AgentState


def load_mock_business_context(state: AgentState) -> dict:
    deps: AgentDependencies = state["_deps"]  # type: ignore[typeddict-item]
    task = deps.task_repository.get_task(state.get("active_task_id"))
    context = deps.business_service.retrieve_context(task.business if task else None)
    return {"business_context_refs": [context["ref"]]}


def build_mock_criteria(state: AgentState) -> dict:
    deps: AgentDependencies = state["_deps"]  # type: ignore[typeddict-item]
    task = deps.task_repository.get_task(state.get("active_task_id"))
    if not task or not task.business or not task.region or not task.target_count:
        return {"errors": [{"node": "build_mock_criteria", "message": "Task requirements are incomplete"}]}
    snapshot_id, _criteria = deps.business_service.build_criteria(
        business=task.business, region=task.region, target_count=task.target_count
    )
    deps.task_repository.set_status(task.task_id, stage=TaskStage.BUSINESS_PLANNING)
    return {"criteria_snapshot_id": snapshot_id, "task_stage": TaskStage.BUSINESS_PLANNING.value}
