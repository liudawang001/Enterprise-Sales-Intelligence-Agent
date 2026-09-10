import logging
import os

from fastapi import FastAPI

from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.knowledge.ingestion.service import DocumentIngestionService
from app.knowledge.repository import InMemoryKnowledgeRepository


def create_app() -> FastAPI:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    application = FastAPI(title="Enterprise Sales Intelligence Agent", version="0.1.0")
    deps = build_dependencies()
    application.state.dependencies = deps
    application.state.graph = build_main_graph(deps)
    knowledge_repository = InMemoryKnowledgeRepository()
    application.state.knowledge_repository = knowledge_repository
    application.state.ingestion_service = DocumentIngestionService(knowledge_repository)
    application.include_router(chat_router)
    application.include_router(documents_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
