from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.routers.slot_router import route_missing_slots
from app.agent.state import AgentState
from app.agent.subgraphs.requirement.nodes import (
    build_clarification,
    clarify_interrupt,
    extract_task_patch,
    merge_task_patch,
    parse_clarification,
    persist_task,
    validate_required_slots,
)


def build_requirement_graph(deps: AgentDependencies, *, checkpointer=None):
    builder = StateGraph(AgentState)

    def with_deps(fn):
        def wrapped(state):
            return fn({**state, "_deps": deps})
        return wrapped

    builder.add_node("extract_task_patch", with_deps(extract_task_patch))
    builder.add_node("merge_task_patch", with_deps(merge_task_patch))
    builder.add_node("validate_required_slots", with_deps(validate_required_slots))
    builder.add_node("build_clarification", with_deps(build_clarification))
    builder.add_node("clarify_interrupt", with_deps(clarify_interrupt))
    builder.add_node("parse_clarification", with_deps(parse_clarification))
    builder.add_node("persist_task", with_deps(persist_task))
    builder.add_edge(START, "extract_task_patch")
    builder.add_edge("extract_task_patch", "merge_task_patch")
    builder.add_edge("merge_task_patch", "validate_required_slots")
    builder.add_conditional_edges("validate_required_slots", route_missing_slots, {
        "MISSING": "build_clarification",
        "COMPLETE": "persist_task",
    })
    builder.add_edge("build_clarification", "clarify_interrupt")
    builder.add_edge("clarify_interrupt", "parse_clarification")
    builder.add_edge("parse_clarification", "merge_task_patch")
    builder.add_edge("persist_task", END)
    return builder.compile(checkpointer=checkpointer)
