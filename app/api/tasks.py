from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from app.security.workspace import scoped_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class ActivateTaskRequest(BaseModel):
    session_id: str = Field(min_length=1)


@router.get("")
async def list_tasks(request: Request, session_id: str | None = Query(default=None)) -> list[dict]:
    return [
        item.model_dump(mode="json")
        for item in request.app.state.dependencies.delivery_query_service.list_tasks(
            session_id
        )
    ]


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request) -> dict:
    task = scoped_task(request, task_id)
    snapshot = request.app.state.dependencies.execution_snapshot_repository.current(task_id)
    try:
        summary = request.app.state.dependencies.delivery_query_service.freeze(
            task_id, task.version
        ).task
    except ValueError:
        summary = request.app.state.dependencies.delivery_query_service.list_tasks(
            task.session_id
        )
        summary = next((item for item in summary if item.task_id == task_id), None)
    return {
        "task": task.model_dump(mode="json"),
        "summary": summary.model_dump(mode="json") if summary else None,
        "current_execution_snapshot": snapshot.model_dump(mode="json") if snapshot else None,
    }


@router.get("/{task_id}/versions")
async def list_task_versions(task_id: str, request: Request) -> list[dict]:
    repository = request.app.state.dependencies.task_repository
    scoped_task(request, task_id)
    service = request.app.state.dependencies.delivery_query_service
    return [
        service.task_version(task_id, item.version).model_dump(mode="json")
        for item in repository.list_versions(task_id)
    ]


@router.get("/{task_id}/versions/{version}")
async def get_task_version(task_id: str, version: int, request: Request) -> dict:
    scoped_task(request, task_id)
    try:
        value = request.app.state.dependencies.delivery_query_service.task_version(
            task_id, version
        )
    except ValueError:
        raise HTTPException(404, "TASK_VERSION_NOT_FOUND")
    return value.model_dump(mode="json")


@router.post("/{task_id}/activate")
async def activate_task(task_id: str, payload: ActivateTaskRequest, request: Request) -> dict:
    scoped_task(request, task_id)
    try:
        task = request.app.state.dependencies.task_repository.activate_task(payload.session_id, task_id)
    except KeyError as exc:
        raise HTTPException(404, "TASK_NOT_FOUND") from exc
    return {"task_id": task.task_id, "active": True, "version": task.version}
