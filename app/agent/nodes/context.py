import logging

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def load_context(state: AgentState, deps: AgentDependencies) -> dict:
    session_id = state.get("session_id", "")
    task = deps.task_repository.get_active_task(session_id)
    logger.info("load_context session_id=%s task_id=%s", session_id, task.task_id if task else None)
    if task is None:
        return {"active_task_id": None}
    return {
        "active_task_id": task.task_id,
        "task_stage": task.stage.value,
        "task_status": task.status.value,
        "task_version": task.version,
    }
