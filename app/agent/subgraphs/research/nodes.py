from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState


def build_mock_search_plan(state: AgentState) -> dict:
    deps: AgentDependencies = state["_deps"]  # type: ignore[typeddict-item]
    task = deps.task_repository.get_task(state.get("active_task_id"))
    return {"search_plan_id": deps.research_service.build_search_plan(task.target_count if task and task.target_count else 5)}


def mock_discovery(state: AgentState) -> dict:
    deps: AgentDependencies = state["_deps"]  # type: ignore[typeddict-item]
    task = deps.task_repository.get_task(state.get("active_task_id"))
    criteria = deps.rule_service.repository.criteria.get(state.get("criteria_snapshot_id")) if state.get("criteria_snapshot_id") else None
    candidate_set_id, leads = deps.research_service.discover(region=task.region if task and task.region else "上海松江", criteria=criteria)
    return {"candidate_set_id": candidate_set_id, "candidate_count": len(leads)}


def mock_enrichment(state: AgentState) -> dict:
    return {"progress": {"research": "enriched"}}


def mock_verification(state: AgentState) -> dict:
    return {"verified_set_id": state.get("candidate_set_id"), "verified_count": state.get("candidate_count", 0), "task_stage": "DISCOVERY"}
