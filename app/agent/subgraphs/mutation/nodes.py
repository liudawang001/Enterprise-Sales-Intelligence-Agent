from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState


def load_current_task(state: AgentState) -> dict:
    return {}


def parse_mutation(state: AgentState) -> dict:
    deps: AgentDependencies = state["_deps"]  # type: ignore[typeddict-item]
    task = deps.task_repository.get_task(state.get("active_task_id"))
    scope, reason = deps.task_service.classify_mutation(state.get("incoming_text", ""), task)
    patch = deps.task_service.parse_mutation(state.get("incoming_text", ""))
    update = {}
    if task and patch.model_dump(exclude_none=True):
        task = deps.task_service.apply_patch(task.task_id, patch)
        update = {"task_version": task.version}
    return {
        "mutation_scope": scope,
        "mutation_reason": reason,
        "task_patch": patch.model_dump(exclude_none=True),
        **update,
    }
