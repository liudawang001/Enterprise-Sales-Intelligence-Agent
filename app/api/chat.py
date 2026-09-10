import logging
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
    return {
        "status": "COMPLETED",
        "task_id": task.task_id if task else None,
        "message": result.get("response_text", ""),
        "data": {"lead_results": result.get("lead_results", []), "citations": result.get("citations", []), "warnings": result.get("rag_warnings", [])},
    }
