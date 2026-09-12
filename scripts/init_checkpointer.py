from __future__ import annotations

import asyncio

from app.runtime.graph_runtime import postgres_connection_string
from app.settings.production import get_settings


async def main() -> None:
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:
        raise SystemExit("Install langgraph-checkpoint-postgres before initialization") from exc
    settings = get_settings()
    async with AsyncPostgresSaver.from_conn_string(
        postgres_connection_string(settings.database.checkpoint_url)
    ) as saver:
        await saver.setup()
    print("LangGraph checkpoint schema initialized")


if __name__ == "__main__":
    asyncio.run(main())
