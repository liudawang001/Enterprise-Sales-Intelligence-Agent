from fastapi import APIRouter, HTTPException, Query, Request

from app.security.workspace import scoped_task

router = APIRouter(prefix="/api")


def _require_task_lead(request: Request, task_id: str, enterprise_id: str) -> None:
    scoped_task(request, task_id)
    try:
        bundle = request.app.state.dependencies.delivery_query_service.freeze(task_id)
    except ValueError as exc:
        raise HTTPException(404, "Task delivery snapshot not found") from exc
    if enterprise_id not in bundle.details:
        raise HTTPException(404, "Enterprise not found in task")


@router.get("/enterprises/{enterprise_id}")
async def get_enterprise(enterprise_id: str, request: Request, task_id: str = Query(...)) -> dict:
    _require_task_lead(request, task_id, enterprise_id)
    deps = request.app.state.dependencies
    enterprise = deps.enterprise_repository.get_enterprise(enterprise_id)
    if not enterprise:
        raise HTTPException(404, "Enterprise not found")
    result = enterprise.model_dump(mode="json")
    profile = deps.evidence_repository.get_profile(enterprise_id)
    result["verified_profile"] = profile.model_dump(mode="json") if profile else None
    return result


@router.get("/enterprises/{enterprise_id}/relations")
async def get_enterprise_relations(enterprise_id: str, request: Request, task_id: str = Query(...)) -> dict:
    _require_task_lead(request, task_id, enterprise_id)
    deps = request.app.state.dependencies
    if not deps.enterprise_repository.get_enterprise(enterprise_id):
        raise HTTPException(404, "Enterprise not found")
    values = deps.enterprise_repository.list_relations(enterprise_id)
    return {"items": [item.model_dump(mode="json") for item in values], "count": len(values)}
