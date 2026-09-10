import logging
import os

from fastapi import FastAPI

from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph
from app.api.chat import router as chat_router
from app.api.criteria import router as criteria_router
from app.api.documents import router as documents_router
from app.api.enterprises import router as enterprises_router
from app.api.evidence import router as evidence_router
from app.api.research import router as research_router
from app.api.rules import router as rules_router
from app.api.scores import router as scores_router
from app.knowledge.ingestion.service import DocumentIngestionService
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.services.knowledge_service import KnowledgeService


def create_app() -> FastAPI:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    application = FastAPI(title="Enterprise Sales Intelligence Agent", version="0.5.0")
    deps = build_dependencies()
    application.state.dependencies = deps
    knowledge_repository = InMemoryKnowledgeRepository()
    application.state.knowledge_repository = knowledge_repository
    application.state.ingestion_service = DocumentIngestionService(knowledge_repository)
    application.state.knowledge_service = KnowledgeService(knowledge_repository)
    deps.knowledge_service = application.state.knowledge_service
    application.state.graph = build_main_graph(deps, knowledge_service=application.state.knowledge_service)
    application.include_router(chat_router)
    application.include_router(documents_router)
    application.include_router(rules_router)
    application.include_router(criteria_router)
    application.include_router(research_router)
    application.include_router(enterprises_router)
    application.include_router(evidence_router)
    application.include_router(scores_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
