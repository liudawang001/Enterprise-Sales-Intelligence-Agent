from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api")


@router.get("/tasks/{task_id}/scores")
async def get_task_scores(task_id: str, request: Request) -> dict:
    values = request.app.state.dependencies.lead_score_repository.list_for_task(task_id)
    return {"items": [item.model_dump(mode="json") for item in values], "count": len(values)}


@router.get("/leads/{enterprise_id}/score")
async def get_lead_score(enterprise_id: str, request: Request) -> dict:
    value = request.app.state.dependencies.lead_score_repository.get_for_enterprise(enterprise_id)
    if not value:
        raise HTTPException(404, "Lead score not found")
    return value.model_dump(mode="json")


@router.get("/leads/{enterprise_id}/score/explain")
async def get_lead_score_explanation(enterprise_id: str, request: Request) -> dict:
    value = request.app.state.dependencies.lead_score_repository.reasons.get(enterprise_id)
    if not value:
        raise HTTPException(404, "Lead score explanation not found")
    return value.model_dump(mode="json")
