from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.exports.models import CreateExportRequest, ExportStatus
from app.exports.service import ExportError
from app.security.auth import principal_from_request
from app.security.workspace import scoped_export, scoped_task

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/fields")
async def export_fields(request: Request) -> dict:
    values = request.app.state.dependencies.export_service.registry.public_fields()
    return {"items": [item.model_dump(mode="json") for item in values]}


@router.post("")
async def create_export(payload: CreateExportRequest, request: Request) -> dict:
    scoped_task(request, payload.task_id)
    try:
        value = request.app.state.dependencies.export_service.create_export(payload)
    except ExportError as exc:
        raise HTTPException(422, str(exc)) from exc
    return value.model_dump(mode="json")


@router.get("/{export_id}")
async def get_export(export_id: str, request: Request) -> dict:
    value = scoped_export(request, export_id)
    return value.model_dump(mode="json")


@router.get("/{export_id}/events")
async def get_export_events(export_id: str, request: Request) -> dict:
    repository = request.app.state.dependencies.export_repository
    scoped_export(request, export_id)
    values = repository.events.get(export_id, [])
    return {"items": values, "count": len(values)}


@router.get("/{export_id}/download")
async def download_export(export_id: str, request: Request):
    deps = request.app.state.dependencies
    value = scoped_export(request, export_id)
    if value.status != ExportStatus.COMPLETED:
        raise HTTPException(409, "EXPORT_NOT_COMPLETED")
    signed_url = getattr(deps.export_service.storage, "signed_url", None)
    if signed_url:
        try:
            return RedirectResponse(signed_url(export_id), status_code=307, headers={"X-Artifact-SHA256": value.sha256 or ""})
        except FileNotFoundError as exc:
            raise HTTPException(404, "EXPORT_ARTIFACT_NOT_FOUND") from exc
    try:
        path = deps.export_service.storage.open(export_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "EXPORT_ARTIFACT_NOT_FOUND") from exc
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=value.file_name,
        headers={"X-Artifact-SHA256": value.sha256 or ""},
    )


task_exports_router = APIRouter(prefix="/api/tasks", tags=["exports"])


@task_exports_router.get("/{task_id}/exports")
async def list_task_exports(task_id: str, request: Request) -> dict:
    deps = request.app.state.dependencies
    scoped_task(request, task_id)
    values = deps.export_repository.list_for_task(task_id, principal_from_request(request).workspace_id)
    return {"items": [item.model_dump(mode="json") for item in values], "count": len(values)}
