from types import SimpleNamespace

import pytest

from app.runtime.lifespan import close_application_resources


class AsyncCloser:
    def __init__(self, name: str, calls: list[str], *, fail: bool = False) -> None:
        self.name = name
        self.calls = calls
        self.fail = fail

    async def close(self) -> None:
        self.calls.append(self.name)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")


class AsyncEngine:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def dispose(self) -> None:
        self.calls.append("postgres_async")


class SyncEngine:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def dispose(self) -> None:
        self.calls.append("postgres_sync")


@pytest.mark.asyncio
async def test_shutdown_closes_every_resource_when_one_closer_fails(caplog) -> None:
    calls: list[str] = []
    app = SimpleNamespace(
        state=SimpleNamespace(
            accepting_work=True,
            tracing=AsyncCloser("langfuse", calls, fail=True),
            redis_manager=AsyncCloser("redis", calls),
            database_engine=AsyncEngine(calls),
            sync_database_engine=SyncEngine(calls),
        )
    )
    graph_runtime = AsyncCloser("checkpointer", calls)

    await close_application_resources(app, graph_runtime)

    assert app.state.accepting_work is False
    assert calls == ["checkpointer", "langfuse", "redis", "postgres_async", "postgres_sync"]
    assert "RESOURCE_SHUTDOWN_FAILED" in caplog.text
