from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api")


@router.get("/tasks/{task_id}/verification")
async def get_task_verification(task_id: str, request: Request) -> dict:
    run = request.app.state.dependencies.evidence_repository.latest_run_for_task(task_id)
    if not run:
        raise HTTPException(404, "Verification run not found")
    return run.model_dump(mode="json")


@router.get("/enterprises/{enterprise_id}/evidence")
async def get_enterprise_evidence(enterprise_id: str, request: Request) -> dict:
    deps = request.app.state.dependencies
    if not deps.enterprise_repository.get_enterprise(enterprise_id):
        raise HTTPException(404, "Enterprise not found")
    values = deps.evidence_repository.list_evidence(enterprise_id)
    return {"items": [item.model_dump(mode="json") for item in values], "count": len(values)}


@router.get("/enterprises/{enterprise_id}/fields/{field_name}/evidence")
async def get_field_evidence(enterprise_id: str, field_name: str, request: Request) -> dict:
    deps = request.app.state.dependencies
    if not deps.enterprise_repository.get_enterprise(enterprise_id):
        raise HTTPException(404, "Enterprise not found")
    values = deps.evidence_repository.list_evidence(enterprise_id, field_name)
    resolved = deps.evidence_repository.resolved_fields.get((enterprise_id, field_name))
    return {
        "field": resolved.model_dump(mode="json") if resolved else None,
        "items": [item.model_dump(mode="json") for item in values],
        "count": len(values),
    }
