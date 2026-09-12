from __future__ import annotations

from fastapi import HTTPException, Request

from app.security.auth import principal_from_request


def scoped_task(request: Request, task_id: str):
    principal = principal_from_request(request)
    task = request.app.state.dependencies.task_repository.get_task(task_id, principal.workspace_id)
    if not task:
        raise HTTPException(404, "TASK_NOT_FOUND")
    return task


def scoped_export(request: Request, export_id: str):
    principal = principal_from_request(request)
    value = request.app.state.dependencies.export_repository.get(export_id, principal.workspace_id)
    if not value:
        raise HTTPException(404, "EXPORT_NOT_FOUND")
    return value
