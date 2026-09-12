from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.agent.subgraphs.mutation.nodes import (
    apply_mutation,
    build_mutation_preview,
    build_reexecution_plan,
    calculate_criteria_diff_node,
    calculate_task_diff_node,
    classify_invalidation_node,
    load_current_task,
    load_reuse_context,
    parse_mutation,
    persist_new_task_version,
    persist_reexecution_plan,
    resolve_target_task,
    route_task_reference,
    task_not_found,
    task_selection_interrupt,
    validate_mutation,
)


def build_mutation_graph(deps: AgentDependencies):
    builder = StateGraph(AgentState)

    def wrap(fn):
        def node(state):
            return fn({**state, "_deps": deps})

        return node

    for name, fn in (
        ("resolve_target_task", resolve_target_task),
        ("task_selection_interrupt", task_selection_interrupt),
        ("task_not_found", task_not_found),
        ("load_current_task", load_current_task),
        ("parse_mutation", parse_mutation),
        ("validate_mutation", validate_mutation),
        ("build_mutation_preview", build_mutation_preview),
        ("calculate_task_diff", calculate_task_diff_node),
        ("calculate_criteria_diff", calculate_criteria_diff_node),
        ("load_reuse_context", load_reuse_context),
        ("classify_invalidation", classify_invalidation_node),
        ("build_reexecution_plan", build_reexecution_plan),
        ("apply_mutation", apply_mutation),
        ("persist_new_task_version", persist_new_task_version),
        ("persist_reexecution_plan", persist_reexecution_plan),
    ):
        builder.add_node(name, wrap(fn))

    builder.add_edge(START, "resolve_target_task")
    builder.add_conditional_edges("resolve_target_task", route_task_reference, {"RESOLVED": "load_current_task", "AMBIGUOUS": "task_selection_interrupt", "NOT_FOUND": "task_not_found"})
    builder.add_edge("task_selection_interrupt", "load_current_task")
    builder.add_edge("task_not_found", END)
    builder.add_edge("load_current_task", "parse_mutation")
    builder.add_edge("parse_mutation", "validate_mutation")
    builder.add_edge("validate_mutation", "build_mutation_preview")
    builder.add_edge("build_mutation_preview", "calculate_task_diff")
    builder.add_edge("calculate_task_diff", "calculate_criteria_diff")
    builder.add_edge("calculate_criteria_diff", "load_reuse_context")
    builder.add_edge("load_reuse_context", "classify_invalidation")
    builder.add_edge("classify_invalidation", "build_reexecution_plan")
    builder.add_edge("build_reexecution_plan", "apply_mutation")
    builder.add_edge("apply_mutation", "persist_new_task_version")
    builder.add_edge("persist_new_task_version", "persist_reexecution_plan")
    builder.add_edge("persist_reexecution_plan", END)
    return builder.compile()
