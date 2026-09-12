import logging
import os
import asyncio
from contextlib import suppress
from uuid import uuid4
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from app.observability.context import get_request_context
from app.observability.metrics import Timer, metrics
from app.runtime.models import ExecutionRunStatus, RunAlreadyClaimedError
from app.infrastructure.events import TaskEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str | None = None


async def _interrupt_payload(result: dict[str, Any], graph, config: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        snapshot = await graph.aget_state(config)
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
    settings = request.app.state.settings
    context = get_request_context()
    principal = request.state.principal
    request_id = payload.request_id or (context.request_id if context else str(uuid4()))
    trace_id = context.trace_id if context else str(uuid4())
    coordinator = deps.execution_coordinator
    try:
        run = await coordinator.claim(request_id=request_id, thread_id=payload.session_id, workspace_id=principal.workspace_id, user_id=principal.user_id, owner=settings.worker_id or "api-worker", lease_seconds=settings.run_lease_seconds, trace_id=trace_id)
    except RunAlreadyClaimedError as exc:
        raise HTTPException(409, "RUN_ALREADY_CLAIMED") from exc
    if run.response_data is not None:
        return run.response_data
    if context:
        context.thread_id = payload.session_id
        context.run_id = run.run_id
        context.fence_token = run.fence_token
    config = {"configurable": {"thread_id": f"{principal.workspace_id}:{payload.session_id}"}, "metadata": {"request_id": request_id, "trace_id": trace_id, "workspace_id": principal.workspace_id, "user_id": principal.user_id, "run_id": run.run_id, "fence_token": run.fence_token}}
    task_store = request.app.state.business_task_store
    if task_store and not deps.task_repository.get_active_task(payload.session_id):
        restored = await task_store.load_active(principal.workspace_id, payload.session_id)
        if restored:
            deps.task_repository.restore_task(*restored)
    snapshot = await graph.aget_state(config)
    has_pending_interrupt = any(getattr(task, "interrupts", ()) for task in snapshot.tasks)
    if has_pending_interrupt:
        metrics.add("agent_resume_total")
    timer = Timer()
    heartbeat = asyncio.create_task(_heartbeat(coordinator, run.run_id, run.fence_token, settings.run_heartbeat_seconds, settings.run_lease_seconds))
    try:
        async with request.app.state.tracing.observation("chat_request", metadata=config["metadata"], input_data=payload.message):
            if has_pending_interrupt:
                command: Any = Command(resume={"text": payload.message})
                result = await graph.ainvoke(command, config=config)
            else:
                result = await graph.ainvoke({"session_id": payload.session_id, "incoming_text": payload.message, "messages": [HumanMessage(content=payload.message)]}, config=config)
    except Exception:
        if has_pending_interrupt:
            metrics.add("agent_resume_failures_total")
        await coordinator.finish(run.run_id, run.fence_token, ExecutionRunStatus.FAILED, error_code="AGENT_RUN_FAILED")
        raise
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
        metrics.add("agent_run_duration_seconds", timer.seconds)
    interrupt = await _interrupt_payload(result, graph, config)
    task = deps.task_repository.get_active_task(payload.session_id)
    if task_store and task:
        await task_store.save(task, deps.task_repository.list_versions(task.task_id))
    if interrupt:
        response = {"status": "WAITING_USER", "task_id": task.task_id if task else None, "interrupt": interrupt}
        metrics.add("agent_interrupts_total", type=interrupt["type"])
        if task:
            await request.app.state.event_service.publish(TaskEvent(task_id=task.task_id, task_version=task.version, workspace_id=principal.workspace_id, run_id=run.run_id, event_type=interrupt["type"], stage=task.stage.value, payload={"status": "WAITING_USER"}))
        await coordinator.finish(run.run_id, run.fence_token, ExecutionRunStatus.WAITING_INTERRUPT, response_data=response)
        return response
    data = {"lead_results": result.get("lead_results", []), "citations": result.get("citations", []), "warnings": result.get("rag_warnings", []) + result.get("warnings", []), "criteria_snapshot_id": result.get("criteria_snapshot_id"), "research_run_id": result.get("research_run_id"), "search_plan_id": result.get("search_plan_id"), "candidate_set_id": result.get("candidate_set_id"), "resolution_run_id": result.get("resolution_run_id"), "verification_run_id": result.get("verification_run_id"), "lead_set_id": result.get("lead_set_id"), "scoring_profile_id": result.get("scoring_profile_id"), "target_task_id": result.get("target_task_id"), "export_spec": result.get("export_spec"), "export_id": result.get("export_id"), "artifact_ref": result.get("artifact_ref"), "mutation_id": result.get("mutation_id"), "reexecution_plan_id": result.get("reexecution_plan_id")}
    if os.getenv("RULE_DEBUG", "false").lower() in {"1", "true", "yes"}:
        data["rule_debug"] = {key: result.get(key, []) for key in ("official_rule_ids", "marketing_rule_ids", "user_rule_ids", "model_suggestion_ids", "normalized_rule_ids", "conflict_ids", "included_rule_ids", "suppressed_rule_ids")}
    response = {
        "status": "COMPLETED",
        "task_id": result.get("target_task_id") or (task.task_id if task else None),
        "message": result.get("response_text", ""),
        "data": data,
    }
    await coordinator.finish(run.run_id, run.fence_token, ExecutionRunStatus.COMPLETED, response_data=response)
    if task:
        await request.app.state.event_service.publish(TaskEvent(task_id=task.task_id, task_version=task.version, workspace_id=principal.workspace_id, run_id=run.run_id, event_type="FINAL", stage=task.stage.value, payload={"status": "COMPLETED"}))
    metrics.add("agent_runs_total", status="COMPLETED")
    return response


async def _heartbeat(coordinator, run_id: str, fence_token: int, interval: int, lease_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval)
        if not await coordinator.heartbeat(run_id, fence_token, lease_seconds):
            return
