import logging
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph
from app.api.chat import router as chat_router
from app.api.criteria import router as criteria_router
from app.api.delivery import router as delivery_router
from app.api.documents import router as documents_router
from app.api.enterprises import router as enterprises_router
from app.api.evidence import router as evidence_router
from app.api.exports import router as exports_router
from app.api.exports import task_exports_router
from app.api.mutations import router as mutations_router
from app.api.research import router as research_router
from app.api.rules import router as rules_router
from app.api.scores import router as scores_router
from app.api.tasks import router as tasks_router
from app.health.checks import router as health_router
from app.infrastructure.events import InMemoryTaskEventRepository, TaskEventService
from app.infrastructure.rate_limit import InMemoryTokenBucket, inbound_rate_key
from app.knowledge.ingestion.service import DocumentIngestionService
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.services.knowledge_service import KnowledgeService
from app.observability.context import RequestContext, reset_request_context, set_request_context
from app.observability.logging import configure_logging
from app.observability.metrics import metrics
from app.observability.tracing import LangfuseTracing
from app.runtime.lifespan import application_lifespan
from app.security.auth import JWTAuthProvider, authenticate_request, require_roles
from app.security.principal import Role
from app.settings.production import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title="Enterprise Sales Intelligence Agent", version="0.8.0", lifespan=application_lifespan(settings)
    )
    application.state.settings = settings
    deps = build_dependencies(settings)
    application.state.dependencies = deps
    knowledge_repository = InMemoryKnowledgeRepository()
    application.state.knowledge_repository = knowledge_repository
    application.state.ingestion_service = DocumentIngestionService(knowledge_repository)
    application.state.knowledge_service = KnowledgeService(knowledge_repository)
    deps.knowledge_service = application.state.knowledge_service
    application.state.graph = build_main_graph(deps, knowledge_service=application.state.knowledge_service)
    application.state.event_repository = InMemoryTaskEventRepository()
    application.state.event_service = TaskEventService(application.state.event_repository)
    deps.event_repository = application.state.event_repository
    application.state.inbound_limiter = InMemoryTokenBucket()
    application.state.tracing = LangfuseTracing(settings)
    application.state.auth_provider = JWTAuthProvider(settings) if settings.auth_mode.value == "jwt" else None
    application.state.accepting_work = True
    application.state.business_task_store = None
    application.state.dependency_status = {
        "checkpointer": "UP",
        "postgres": "UNKNOWN",
        "redis": "UNKNOWN",
        "langfuse": "UNKNOWN",
    }

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Trace-ID", "Last-Event-ID"],
    )

    @application.middleware("http")
    async def production_boundary(request: Request, call_next):
        started = monotonic()
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
        public_paths = {"/health/live", "/health/ready", "/health/dependencies", "/metrics"}
        try:
            principal = (
                authenticate_request(request, settings, application.state.auth_provider)
                if request.url.path not in public_paths
                else None
            )
            request.state.principal = principal
            if principal is not None and request.method not in {"GET", "HEAD", "OPTIONS"}:
                if request.url.path.startswith("/api/documents"):
                    require_roles(principal, Role.ADMIN)
                else:
                    require_roles(principal, Role.ADMIN, Role.ANALYST)
            elif principal is not None and request.url.path.startswith("/api/"):
                require_roles(principal, Role.ADMIN, Role.ANALYST, Role.VIEWER)
            context = RequestContext(request_id=request_id, trace_id=trace_id, principal=principal)
            token = set_request_context(context)
            if request.url.path in {"/api/chat", "/api/exports", "/api/documents"} and request.method == "POST":
                decision = await application.state.inbound_limiter.acquire(
                    inbound_rate_key(principal.workspace_id, principal.user_id, request.url.path),
                    capacity=120,
                    refill_per_second=2,
                )
                if not decision.allowed:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "API_RATE_LIMITED",
                            "error": {
                                "code": "API_RATE_LIMITED",
                                "message": "Request rate exceeded",
                                "trace_id": trace_id,
                            },
                        },
                        headers={"Retry-After": str(max(1, decision.retry_after_ms // 1000))},
                    )
            try:
                response = await call_next(request)
            finally:
                reset_request_context(token)
        except HTTPException as exc:
            response = await http_exception_handler(request, exc)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        response.headers["X-Frame-Options"] = "DENY"
        metrics.add(
            "http_requests_total", method=request.method, route=request.url.path, status=str(response.status_code)
        )
        metrics.add("http_request_duration_seconds", monotonic() - started, method=request.method)
        if response.status_code >= 400:
            metrics.add("http_errors_total", status=str(response.status_code))
        return response

    application.include_router(chat_router)
    application.include_router(documents_router)
    application.include_router(delivery_router)
    application.include_router(rules_router)
    application.include_router(criteria_router)
    application.include_router(research_router)
    application.include_router(enterprises_router)
    application.include_router(evidence_router)
    application.include_router(exports_router)
    application.include_router(task_exports_router)
    application.include_router(scores_router)
    application.include_router(tasks_router)
    application.include_router(mutations_router)
    application.include_router(health_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
        logging.getLogger(__name__).exception("UNEXPECTED_ERROR", extra={"error_code": "UNEXPECTED_ERROR"})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "UNEXPECTED_ERROR", "message": "Unexpected server error", "trace_id": trace_id}},
        )

    return application


app = create_app()
