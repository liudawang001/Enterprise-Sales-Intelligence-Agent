import logging
import os
from typing import Any

from fastapi import APIRouter, Request
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


def _interrupt_payload(result: dict[str, Any], graph, config: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        snapshot = graph.get_state(config)
        interrupts = [item for task in snapshot.tasks for item in getattr(task, "interrupts", ())]
    if not interrupts:
        return None
    raw = interrupts[0]
    value = getattr(raw, "value", raw)
    if not isinstance(value, dict):
        value = {"type": "CLARIFICATION_REQUIRED", "question": str(value), "missing_slots": []}
    question = value.get("question", "")
    if isinstance(question, dict):
        question = question.get("text", "")
    return {
        "type": value.get("type", "CLARIFICATION_REQUIRED"),
        "question": question,
        "missing_slots": value.get("missing_slots", []),
        "conflicts": value.get("conflicts", []),
        "candidate_tasks": value.get("candidate_tasks", []),
    }


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request) -> dict[str, Any]:
    graph = request.app.state.graph
    deps = request.app.state.dependencies
    config = {"configurable": {"thread_id": payload.session_id}}
    snapshot = graph.get_state(config)
    has_pending_interrupt = any(getattr(task, "interrupts", ()) for task in snapshot.tasks)
    if has_pending_interrupt:
        command: Any = Command(resume={"text": payload.message})
        result = await graph.ainvoke(command, config=config)
    else:
        result = await graph.ainvoke(
            {
                "session_id": payload.session_id,
                "incoming_text": payload.message,
                "messages": [HumanMessage(content=payload.message)],
            },
            config=config,
        )
    interrupt = _interrupt_payload(result, graph, config)
    task = deps.task_repository.get_active_task(payload.session_id)
    if interrupt:
        return {"status": "WAITING_USER", "task_id": task.task_id if task else None, "interrupt": interrupt}
    data = {"lead_results": result.get("lead_results", []), "citations": result.get("citations", []), "warnings": result.get("rag_warnings", []) + result.get("warnings", []), "criteria_snapshot_id": result.get("criteria_snapshot_id"), "research_run_id": result.get("research_run_id"), "search_plan_id": result.get("search_plan_id"), "candidate_set_id": result.get("candidate_set_id"), "resolution_run_id": result.get("resolution_run_id"), "verification_run_id": result.get("verification_run_id"), "lead_set_id": result.get("lead_set_id"), "scoring_profile_id": result.get("scoring_profile_id"), "target_task_id": result.get("target_task_id"), "export_spec": result.get("export_spec"), "export_id": result.get("export_id"), "artifact_ref": result.get("artifact_ref"), "mutation_id": result.get("mutation_id"), "reexecution_plan_id": result.get("reexecution_plan_id")}
    if os.getenv("RULE_DEBUG", "false").lower() in {"1", "true", "yes"}:
        data["rule_debug"] = {key: result.get(key, []) for key in ("official_rule_ids", "marketing_rule_ids", "user_rule_ids", "model_suggestion_ids", "normalized_rule_ids", "conflict_ids", "included_rule_ids", "suppressed_rule_ids")}
    return {
        "status": "COMPLETED",
        "task_id": result.get("target_task_id") or (task.task_id if task else None),
        "message": result.get("response_text", ""),
        "data": data,
    }
