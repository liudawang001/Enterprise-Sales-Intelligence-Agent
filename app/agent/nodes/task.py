import logging

from app.agent.dependencies import AgentDependencies
from app.agent.enums import TaskStage, TaskStatus
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_lead_task(state: AgentState, deps: AgentDependencies) -> dict:
    if state.get("active_task_id"):
        return {}
    task = deps.task_service.create_or_get_task(state["session_id"])
    logger.info("create_lead_task task_id=%s session_id=%s", task.task_id, task.session_id)
    return {
        "active_task_id": task.task_id,
        "task_stage": task.stage.value,
        "task_status": task.status.value,
        "task_version": task.version,
    }
