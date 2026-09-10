import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api")


def _repository(request: Request):
    return request.app.state.dependencies.research_service.repository


@router.get("/tasks/{task_id}/research")
async def get_task_research(task_id: str, request: Request) -> dict:
    run = _repository(request).get_run_for_task(task_id)
    if not run:
        raise HTTPException(404, "Research run not found")
    return run.model_dump(mode="json")


@router.get("/tasks/{task_id}/candidates")
async def get_task_candidates(task_id: str, request: Request) -> dict:
    repository = _repository(request)
    run = repository.get_run_for_task(task_id)
    if not run:
        raise HTTPException(404, "Research run not found")
    values = repository.get_candidates(
        run.researched_candidate_set_id
        or run.filtered_candidate_set_id
        or run.raw_candidate_set_id
    )
    return {
        "items": [
            {
                "candidate_id": v.candidate_id,
                "company_name": v.source_name,
                "status": v.status,
                "provisional": True,
                "source_count": len(repository.get_sources(v.candidate_id)),
            }
            for v in values
        ],
        "count": len(values),
    }


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str, request: Request) -> dict:
    repository = _repository(request)
    value = repository.get_candidate(candidate_id)
    if not value:
        raise HTTPException(404, "Candidate not found")
    result = value.model_dump(mode="json")
    result.update(
        {
            "company_name": value.source_name,
            "provisional": True,
            "source_count": len(repository.get_sources(candidate_id)),
        }
    )
    return result


@router.get("/candidates/{candidate_id}/sources")
async def get_candidate_sources(candidate_id: str, request: Request) -> dict:
    if not _repository(request).get_candidate(candidate_id):
        raise HTTPException(404, "Candidate not found")
    values = _repository(request).get_sources(candidate_id)
    return {"items": [v.model_dump(mode="json") for v in values], "count": len(values)}


@router.get("/research/{research_run_id}/plan")
async def get_research_plan(research_run_id: str, request: Request) -> dict:
    repository = _repository(request)
    run = repository.runs.get(research_run_id)
    if not run or not run.search_plan_id:
        raise HTTPException(404, "Research plan not found")
    plan = repository.plans[run.search_plan_id]
    return {
        "plan": plan.model_dump(mode="json"),
        "explain": plan.pushdown_explain,
        "used_budget": run.used_budget,
    }


@router.get("/research/{research_run_id}/events")
async def research_events(research_run_id: str, request: Request):
    run = _repository(request).runs.get(research_run_id)
    if not run:
        raise HTTPException(404, "Research run not found")

    async def stream():
        events = _repository(request).events.get(research_run_id) or [
            {
                "event": "RESEARCH_PROGRESS",
                "stage": run.stage,
                "status": run.status,
                "used_budget": run.used_budget,
            }
        ]
        for payload in events:
            yield f"event: {payload['event']}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
