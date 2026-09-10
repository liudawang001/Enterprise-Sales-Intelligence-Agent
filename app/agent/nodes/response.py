from app.agent.dependencies import AgentDependencies
from app.agent.enums import TaskStage, TaskStatus
from app.agent.state import AgentState


def compose_lead_response(state: AgentState, deps: AgentDependencies) -> dict:
    task = deps.task_repository.get_task(state.get("active_task_id"))
    leads = state.get("lead_results", [])
    if not task:
        return {"response_text": "当前没有可用的潜客任务。"}
    top_name = leads[0].get("company_name") if leads else "暂无"
    deps.task_repository.set_status(task.task_id, stage=TaskStage.COMPLETED, status=TaskStatus.COMPLETED)
    return {
        "task_stage": TaskStage.COMPLETED.value,
        "task_status": TaskStatus.COMPLETED.value,
        "response_text": (
            "已根据当前条件完成模拟潜客发现。\n\n"
            f"业务：{task.business}\n区域：{task.region}\n目标数量：{task.target_count}\n\n"
            f"Phase 3 Criteria Mock Research 当前返回{len(leads)}条示例潜客，其中评分最高的是{top_name}。\n\n"
            "当前结果来自Mock数据，尚未接入真实企业信息API。"
        ),
    }
