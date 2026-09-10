import logging
import os

from fastapi import FastAPI

from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph
from app.api.chat import router as chat_router


def create_app() -> FastAPI:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    application = FastAPI(title="Enterprise Sales Intelligence Agent", version="0.1.0")
    deps = build_dependencies()
    application.state.dependencies = deps
    application.state.graph = build_main_graph(deps)
    application.include_router(chat_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
