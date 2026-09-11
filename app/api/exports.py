from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.exports.models import CreateExportRequest, ExportStatus
from app.exports.service import ExportError

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/fields")
async def export_fields(request: Request) -> dict:
    values = request.app.state.dependencies.export_service.registry.public_fields()
    return {"items": [item.model_dump(mode="json") for item in values]}


@router.post("")
async def create_export(payload: CreateExportRequest, request: Request) -> dict:
    try:
        value = request.app.state.dependencies.export_service.create_export(payload)
    except ExportError as exc:
        raise HTTPException(422, str(exc)) from exc
    return value.model_dump(mode="json")


@router.get("/{export_id}")
async def get_export(export_id: str, request: Request) -> dict:
    value = request.app.state.dependencies.export_repository.get(export_id)
    if not value:
        raise HTTPException(404, "EXPORT_NOT_FOUND")
    return value.model_dump(mode="json")


@router.get("/{export_id}/events")
async def get_export_events(export_id: str, request: Request) -> dict:
    repository = request.app.state.dependencies.export_repository
    if not repository.get(export_id):
        raise HTTPException(404, "EXPORT_NOT_FOUND")
    values = repository.events.get(export_id, [])
    return {"items": values, "count": len(values)}


@router.get("/{export_id}/download")
async def download_export(export_id: str, request: Request):
    deps = request.app.state.dependencies
    value = deps.export_repository.get(export_id)
    if not value:
        raise HTTPException(404, "EXPORT_NOT_FOUND")
    if value.status != ExportStatus.COMPLETED:
        raise HTTPException(409, "EXPORT_NOT_COMPLETED")
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
    if not deps.task_repository.get_task(task_id):
        raise HTTPException(404, "TASK_NOT_FOUND")
    values = deps.export_repository.list_for_task(task_id)
    return {"items": [item.model_dump(mode="json") for item in values], "count": len(values)}
