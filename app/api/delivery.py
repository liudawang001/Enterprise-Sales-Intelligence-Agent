from __future__ import annotations

import json
import asyncio

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from app.infrastructure.events import TaskEvent
from app.observability.context import get_request_context
from app.observability.metrics import metrics
from app.security.auth import principal_from_request
from app.security.workspace import scoped_task

from app.delivery.queries import DeliveryNotFoundError

router = APIRouter(prefix="/api", tags=["delivery"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _http_error(exc: Exception) -> HTTPException:
    code = str(exc)
    status = 404 if code.endswith("NOT_FOUND") else 400
    return HTTPException(status, code)


@router.get("/tasks/{task_id}/versions/{version}/leads")
async def list_version_leads(
    task_id: str,
    version: int,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    sort_by: str = Query(default="rank"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    verification_status: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    industry: str | None = Query(default=None),
    has_public_phone: bool | None = Query(default=None),
    has_website: bool | None = Query(default=None),
) -> dict:
    scoped_task(request, task_id)
    try:
        value = request.app.state.dependencies.delivery_query_service.lead_page(
            task_id,
            version,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            verification_status=verification_status,
            min_score=min_score,
            industry=industry,
            has_public_phone=has_public_phone,
            has_website=has_website,
        )
    except (DeliveryNotFoundError, ValueError) as exc:
        raise _http_error(exc) from exc
    return value.model_dump(mode="json")


@router.get("/tasks/{task_id}/versions/{version}/leads/{enterprise_id}")
async def get_version_lead(
    task_id: str, version: int, enterprise_id: str, request: Request
) -> dict:
    scoped_task(request, task_id)
    try:
        bundle = request.app.state.dependencies.delivery_query_service.freeze(
            task_id, version
        )
    except DeliveryNotFoundError as exc:
        raise _http_error(exc) from exc
    value = bundle.details.get(enterprise_id)
    if not value:
        raise HTTPException(404, "LEAD_NOT_FOUND_IN_TASK_VERSION")
    return value.model_dump(mode="json")


@router.get("/tasks/{task_id}/versions/{version}/leads/{enterprise_id}/score")
async def get_version_lead_score(
    task_id: str, version: int, enterprise_id: str, request: Request
) -> dict:
    scoped_task(request, task_id)
    try:
        bundle = request.app.state.dependencies.delivery_query_service.freeze(
            task_id, version
        )
    except DeliveryNotFoundError as exc:
        raise _http_error(exc) from exc
    value = bundle.details.get(enterprise_id)
    if not value:
        raise HTTPException(404, "LEAD_SCORE_NOT_FOUND")
    return {
        "snapshot_id": bundle.snapshot.snapshot_id,
        "task_id": task_id,
        "task_version": version,
        "score_set_id": bundle.snapshot.lead_score_set_id,
        **value.score.model_dump(mode="json"),
    }


@router.get("/tasks/{task_id}/events")
async def get_task_status(task_id: str, request: Request) -> dict:
    deps = request.app.state.dependencies
    task = scoped_task(request, task_id)
    execution = deps.execution_snapshot_repository.current(task_id)
    research = deps.research_service.repository.get_run_for_task(task_id)
    return {
        "task_id": task_id,
        "task_version": task.version,
        "stage": task.stage.value,
        "status": task.status.value,
        "execution_snapshot_id": execution.snapshot_id if execution else None,
        "progress": {
            "event": "FINAL" if task.status.value == "COMPLETED" else "TASK_STATUS",
            "stage": research.stage if research else task.stage.value,
            "used_budget": research.used_budget if research else {},
        },
    }


@router.get("/tasks/{task_id}/events/stream")
async def stream_task_events(task_id: str, request: Request, last_event_id: str | None = Query(default=None)):
    deps = request.app.state.dependencies
    task = scoped_task(request, task_id)
    principal = principal_from_request(request)
    last_event_id = request.headers.get("Last-Event-ID") or last_event_id

    async def stream():
        metrics.add("active_sse_connections", 1)
        try:
            durable = await request.app.state.event_service.replay(task_id, last_event_id)
            seen = set()
            for item in durable:
                seen.add(item.event_id)
                yield f"id: {item.event_id}\nevent: {item.event_type}\ndata: {item.model_dump_json()}\n\n"
            research = deps.research_service.repository.get_run_for_task(task_id)
            events = deps.research_service.repository.events.get(research.research_run_id, []) if research else []
            for event in events:
                payload = {"event": event.get("event", "TASK_STATUS"), "stage": event.get("stage", research.stage if research else task.stage.value), "status": task.status.value, **{key: value for key, value in event.items() if key != "event"}}
                yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            final = {"event": "FINAL" if task.status.value == "COMPLETED" else "TASK_STATUS", "stage": task.stage.value, "status": task.status.value}
            yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
            redis_client = getattr(getattr(request.app.state, "redis_manager", None), "client", None)
            if redis_client and task.status.value != "COMPLETED":
                stream_id = "$"
                while not await request.is_disconnected():
                    rows = await redis_client.xread({f"task-events:{task_id}": stream_id}, block=15000, count=50)
                    if not rows:
                        yield ": keepalive\n\n"
                        continue
                    for _, messages in rows:
                        for stream_id, fields in messages:
                            raw = fields.get(b"event") or fields.get("event")
                            item = TaskEvent.model_validate_json(raw)
                            if item.workspace_id == principal.workspace_id and item.event_id not in seen:
                                seen.add(item.event_id)
                                yield f"id: {item.event_id}\nevent: {item.event_type}\ndata: {item.model_dump_json()}\n\n"
        finally:
            metrics.add("active_sse_connections", -1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
