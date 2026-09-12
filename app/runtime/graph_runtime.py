from __future__ import annotations

from contextlib import AsyncExitStack

from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import build_main_graph


def postgres_connection_string(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


class GraphRuntime:
    def __init__(self, deps, settings) -> None:
        self.deps = deps
        self.settings = settings
        self._stack = AsyncExitStack()
        self.checkpointer = None
        self.graph = None

    async def start(self):
        if self.settings.graph_checkpointer == "postgres":
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            except ImportError as exc:
                raise RuntimeError("langgraph-checkpoint-postgres is required for production checkpointing") from exc
            manager = AsyncPostgresSaver.from_conn_string(
                postgres_connection_string(self.settings.database.checkpoint_url)
            )
            self.checkpointer = await self._stack.enter_async_context(manager)
        else:
            self.checkpointer = InMemorySaver()
        self.graph = build_main_graph(
            self.deps, checkpointer=self.checkpointer, knowledge_service=self.deps.knowledge_service
        )
        return self.graph

    async def close(self) -> None:
        await self._stack.aclose()
