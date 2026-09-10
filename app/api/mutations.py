from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.domain.task import TaskPatch
from app.mutation.service import InvalidTaskPatchError
from app.repositories.mock_task_repository import TaskVersionConflictError

router = APIRouter(prefix="/api", tags=["mutations"])


class StructuredMutationRequest(BaseModel):
    base_version: int = Field(ge=1)
    patch: TaskPatch
    source_message_id: str = Field(default_factory=lambda: str(uuid4()))


@router.post("/tasks/{task_id}/mutations")
async def create_mutation(task_id: str, payload: StructuredMutationRequest, request: Request) -> dict:
    service = request.app.state.dependencies.mutation_service
    try:
        mutation, _ = service.mutate(task_id=task_id, base_version=payload.base_version, source_message_id=payload.source_message_id, patch=payload.patch)
    except KeyError as exc:
        raise HTTPException(404, "TASK_NOT_FOUND") from exc
    except TaskVersionConflictError as exc:
        raise HTTPException(409, "TASK_VERSION_CONFLICT") from exc
    except InvalidTaskPatchError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "mutation_id": mutation.mutation_id,
        "target_version": mutation.target_version,
        "scope": mutation.scope,
        "reexecution_plan_id": mutation.reexecution_plan_id,
    }


@router.get("/tasks/{task_id}/mutations/{mutation_id}")
async def get_mutation(task_id: str, mutation_id: str, request: Request) -> dict:
    value = request.app.state.dependencies.mutation_repository.get_mutation(mutation_id)
    if not value or value.task_id != task_id:
        raise HTTPException(404, "MUTATION_NOT_FOUND")
    plan = request.app.state.dependencies.mutation_repository.get_plan(value.reexecution_plan_id)
    result = value.model_dump(mode="json")
    result["reason_codes"] = plan.reason_codes if plan else []
    result["reused_artifacts"] = plan.reused_artifact_ids if plan else []
    result["rebuild_steps"] = plan.steps if plan else []
    return result


@router.get("/reexecution/{plan_id}")
async def get_reexecution(plan_id: str, request: Request) -> dict:
    value = request.app.state.dependencies.mutation_repository.get_plan(plan_id)
    if not value:
        raise HTTPException(404, "REEXECUTION_PLAN_NOT_FOUND")
    result = value.model_dump(mode="json")
    result["target_version"] = value.next_version
    return result
