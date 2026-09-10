from app.agent.dependencies import AgentDependencies
from app.agent.enums import TaskStage, TaskStatus
from app.agent.state import AgentState


def compose_lead_response(state: AgentState, deps: AgentDependencies) -> dict:
    task = deps.task_repository.get_task(state.get("active_task_id"))
    leads = state.get("lead_results", [])
    if not task:
        return {"response_text": "当前没有可用的潜客任务。"}
    if state.get("task_version") != task.version:
        return {
            "response_text": "该执行已被更新的任务版本取代，结果已保留但未设为当前结果。",
            "warnings": ["STALE_EXECUTION"],
        }
    top_name = leads[0].get("company_name") if leads else "暂无"
    deps.task_repository.set_status(task.task_id, stage=TaskStage.COMPLETED, status=TaskStatus.COMPLETED)
    return {
        "task_stage": TaskStage.COMPLETED.value,
        "task_status": TaskStatus.COMPLETED.value,
        "response_text": (
            "已根据当前条件完成企业潜客发现。\n\n"
            f"业务：{task.business}\n区域：{task.region}\n目标数量：{task.target_count}\n\n"
            f"当前返回{len(leads)}条已归一化、字段级核验并完成确定性评分的企业，其中优先级最高的是{top_name}。\n\n"
            "结果保留 Evidence 来源、字段冲突状态与评分组件，可通过企业和评分 API 逐层追溯。"
        ),
    }
