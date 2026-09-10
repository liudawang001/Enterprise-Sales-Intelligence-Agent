from __future__ import annotations

from langgraph.types import interrupt

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState


def make_resolve_read_task(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        resolver = deps.task_reference_resolver
        reference = resolver.parse(state.get("incoming_text", ""), active_task_id=state.get("active_task_id"))
        resolution = resolver.resolve(state.get("session_id", ""), reference, active_task_id=state.get("active_task_id"))
        task_id = resolution.task_id
        if resolution.status == "AMBIGUOUS":
            answer = interrupt({
                "type": "TASK_SELECTION_REQUIRED",
                "candidate_tasks": [item.model_dump(mode="json") for item in resolution.candidates],
                "question": "你希望查询哪个营销任务？",
            })
            text = answer.get("text", "") if isinstance(answer, dict) else str(answer)
            task_id = answer.get("task_id") if isinstance(answer, dict) else None
            if not task_id:
                matches = [item for item in resolution.candidates if item.task_id in text or (item.business and item.business in text)]
                task_id = matches[0].task_id if len(matches) == 1 else None
        if not task_id:
            raise ValueError("TASK_REFERENCE_AMBIGUOUS")
        snapshot = deps.execution_snapshot_repository.current(task_id)
        return {
            "target_task_id": task_id,
            "task_reference": reference.model_dump(mode="json"),
            "task_reference_status": "RESOLVED",
            "execution_snapshot_id": snapshot.snapshot_id if snapshot else None,
        }

    return node
