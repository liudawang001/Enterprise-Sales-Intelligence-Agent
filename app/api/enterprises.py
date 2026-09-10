from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api")


@router.get("/enterprises/{enterprise_id}")
async def get_enterprise(enterprise_id: str, request: Request) -> dict:
    deps = request.app.state.dependencies
    enterprise = deps.enterprise_repository.get_enterprise(enterprise_id)
    if not enterprise:
        raise HTTPException(404, "Enterprise not found")
    result = enterprise.model_dump(mode="json")
    profile = deps.evidence_repository.get_profile(enterprise_id)
    result["verified_profile"] = profile.model_dump(mode="json") if profile else None
    return result


@router.get("/enterprises/{enterprise_id}/relations")
async def get_enterprise_relations(enterprise_id: str, request: Request) -> dict:
    deps = request.app.state.dependencies
    if not deps.enterprise_repository.get_enterprise(enterprise_id):
        raise HTTPException(404, "Enterprise not found")
    values = deps.enterprise_repository.list_relations(enterprise_id)
    return {"items": [item.model_dump(mode="json") for item in values], "count": len(values)}
