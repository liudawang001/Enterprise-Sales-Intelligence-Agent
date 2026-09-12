from fastapi import APIRouter, HTTPException, Query, Request

from app.security.workspace import scoped_task

router = APIRouter(prefix="/api")


@router.get("/tasks/{task_id}/scores")
async def get_task_scores(task_id: str, request: Request) -> dict:
    scoped_task(request, task_id)
    values = request.app.state.dependencies.lead_score_repository.list_for_task(task_id)
    return {"items": [item.model_dump(mode="json") for item in values], "count": len(values)}


@router.get("/leads/{enterprise_id}/score")
async def get_lead_score(enterprise_id: str, request: Request, task_id: str = Query(...)) -> dict:
    scoped_task(request, task_id)
    repository = request.app.state.dependencies.lead_score_repository
    value = next(
        (item for item in repository.list_for_task(task_id) if item.enterprise_id == enterprise_id),
        None,
    )
    if not value:
        raise HTTPException(404, "Lead score not found")
    return value.model_dump(mode="json")


@router.get("/leads/{enterprise_id}/score/explain")
async def get_lead_score_explanation(enterprise_id: str, request: Request, task_id: str = Query(...)) -> dict:
    scoped_task(request, task_id)
    repository = request.app.state.dependencies.lead_score_repository
    score = next(
        (item for item in repository.list_for_task(task_id) if item.enterprise_id == enterprise_id),
        None,
    )
    value = repository.reason_for_score(score) if score else None
    if not value:
        raise HTTPException(404, "Lead score explanation not found")
    return value.model_dump(mode="json")
