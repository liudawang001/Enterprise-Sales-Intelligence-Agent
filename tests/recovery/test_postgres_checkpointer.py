import os
from typing import TypedDict
from uuid import uuid4

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class RecoveryState(TypedDict, total=False):
    value: str
    answer: str


def build_graph(checkpointer):
    builder = StateGraph(RecoveryState)
    builder.add_node("node_a", lambda state: {"value": "persisted"})

    def wait_for_user(_state):
        return {"answer": interrupt({"type": "CLARIFICATION_REQUIRED"})["text"]}

    builder.add_node("clarify_interrupt", wait_for_user)
    builder.add_edge(START, "node_a")
    builder.add_edge("node_a", "clarify_interrupt")
    builder.add_edge("clarify_interrupt", END)
    return builder.compile(checkpointer=checkpointer)


@pytest.mark.integration
@pytest.mark.recovery
@pytest.mark.asyncio
async def test_interrupt_survives_checkpointer_runtime_restart() -> None:
    url = os.getenv("TEST_CHECKPOINT_DATABASE_URL")
    if not url:
        pytest.skip("TEST_CHECKPOINT_DATABASE_URL is not configured")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    thread_id = f"recovery-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        await saver.setup()
        first = await build_graph(saver).ainvoke({}, config=config)
        assert first["value"] == "persisted"
        assert first["__interrupt__"]
    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        resumed = await build_graph(saver).ainvoke(Command(resume={"text": "上海松江"}), config=config)
    assert resumed == {"value": "persisted", "answer": "上海松江"}
