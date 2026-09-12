from fastapi import APIRouter, HTTPException, Query, Request

from app.security.workspace import scoped_task

router = APIRouter(prefix="/api")


@router.get("/tasks/{task_id}/verification")
async def get_task_verification(task_id: str, request: Request) -> dict:
    scoped_task(request, task_id)
    run = request.app.state.dependencies.evidence_repository.latest_run_for_task(task_id)
    if not run:
        raise HTTPException(404, "Verification run not found")
    return run.model_dump(mode="json")


@router.get("/enterprises/{enterprise_id}/evidence")
async def get_enterprise_evidence(
    enterprise_id: str,
    request: Request,
    field_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    version: int | None = Query(default=None),
    snapshot_id: str | None = Query(default=None),
) -> dict:
    deps = request.app.state.dependencies
    if not task_id and not snapshot_id:
        raise HTTPException(400, "TASK_CONTEXT_REQUIRED")
    if task_id:
        scoped_task(request, task_id)
    if not deps.enterprise_repository.get_enterprise(enterprise_id):
        raise HTTPException(404, "Enterprise not found")
    if snapshot_id or task_id:
        try:
            bundle = (
                deps.delivery_query_service.get_bundle(snapshot_id)
                if snapshot_id
                else deps.delivery_query_service.freeze(task_id, version)
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        scoped_task(request, bundle.snapshot.task_id)
        if task_id and bundle.snapshot.task_id != task_id:
            raise HTTPException(404, "SNAPSHOT_NOT_FOUND")
        detail = bundle.details.get(enterprise_id)
        if not detail:
            raise HTTPException(404, "LEAD_NOT_FOUND_IN_TASK_VERSION")
        field_statuses = detail.lead.field_statuses
        values = [
            item
            for item in detail.evidence
            if (not field_name or item.field_name == field_name)
            and (not source_type or item.source_type == source_type)
            and (not status or field_statuses.get(item.field_name) == status)
        ]
        return {
            "snapshot_id": bundle.snapshot.snapshot_id,
            "task_id": bundle.snapshot.task_id,
            "task_version": bundle.snapshot.task_version,
            "items": [item.model_dump(mode="json") for item in values],
            "count": len(values),
        }
    raise HTTPException(400, "TASK_CONTEXT_REQUIRED")


@router.get("/enterprises/{enterprise_id}/fields/{field_name}/evidence")
async def get_field_evidence(
    enterprise_id: str,
    field_name: str,
    request: Request,
    task_id: str = Query(...),
) -> dict:
    deps = request.app.state.dependencies
    scoped_task(request, task_id)
    try:
        bundle = deps.delivery_query_service.freeze(task_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if enterprise_id not in bundle.details:
        raise HTTPException(404, "LEAD_NOT_FOUND_IN_TASK_VERSION")
    if not deps.enterprise_repository.get_enterprise(enterprise_id):
        raise HTTPException(404, "Enterprise not found")
    values = deps.evidence_repository.list_evidence(enterprise_id, field_name)
    resolved = deps.evidence_repository.resolved_fields.get((enterprise_id, field_name))
    return {
        "field": resolved.model_dump(mode="json") if resolved else None,
        "items": [item.model_dump(mode="json") for item in values],
        "count": len(values),
    }
