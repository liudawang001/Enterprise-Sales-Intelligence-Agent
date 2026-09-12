from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from app.observability.metrics import metrics

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict:
    return {"status": "UP"}


@router.get("/health/ready")
async def ready(request: Request, response: Response) -> dict:
    statuses = getattr(request.app.state, "dependency_status", {})
    hard = [statuses.get("checkpointer", "UP")]
    if request.app.state.settings.graph_checkpointer == "postgres":
        hard.append(statuses.get("postgres", "DOWN"))
    if request.app.state.settings.redis_required:
        hard.append(statuses.get("redis", "DOWN"))
    is_ready = getattr(request.app.state, "accepting_work", True) and all(value == "UP" for value in hard)
    if not is_ready:
        response.status_code = 503
    return {"status": "UP" if is_ready else "DOWN"}


@router.get("/health/dependencies")
async def dependencies(request: Request) -> dict:
    statuses = {
        "postgres": "UNKNOWN",
        "checkpointer": "UNKNOWN",
        "redis": "UNKNOWN",
        "langfuse": "UNKNOWN",
        "enterprise_provider": "UP",
        "map_provider": "UP",
        "web_search_provider": "UP",
    }
    statuses.update(getattr(request.app.state, "dependency_status", {}))
    engine = getattr(request.app.state, "database_engine", None)
    if engine is not None:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            statuses["postgres"] = "UP"
        except Exception:
            statuses["postgres"] = "DOWN"
    redis_manager = getattr(request.app.state, "redis_manager", None)
    if redis_manager and redis_manager.client:
        try:
            await redis_manager.client.ping()
            statuses["redis"] = "UP"
        except Exception:
            statuses["redis"] = "DEGRADED"
    return {"status": "UP", "dependencies": statuses}


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    return metrics.render()
