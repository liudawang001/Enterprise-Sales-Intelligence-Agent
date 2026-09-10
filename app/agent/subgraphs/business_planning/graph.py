from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.agent.subgraphs.business_planning import nodes


def build_business_planning_graph(deps: AgentDependencies, *, checkpointer=None):
    builder = StateGraph(AgentState)

    def wrap(fn):
        def node(state):
            return fn({**state, "_deps": deps})
        return node

    names = ["load_task_requirements", "retrieve_business_evidence", "extract_official_rules", "load_marketing_rules", "build_user_rules", "generate_model_suggestions", "normalize_rules", "validate_rules", "detect_conflicts", "build_conflict_question", "conflict_interrupt", "apply_conflict_resolution", "resolve_rule_set", "compile_criteria", "validate_criteria_node", "persist_criteria_snapshot"]
    for name in names:
        builder.add_node(name, wrap(getattr(nodes, name)))
    builder.add_edge(START, "load_task_requirements")
    builder.add_edge("load_task_requirements", "retrieve_business_evidence")
    builder.add_edge("retrieve_business_evidence", "extract_official_rules")
    builder.add_edge("extract_official_rules", "load_marketing_rules")
    builder.add_edge("load_marketing_rules", "build_user_rules")
    builder.add_edge("build_user_rules", "generate_model_suggestions")
    builder.add_edge("generate_model_suggestions", "normalize_rules")
    builder.add_edge("normalize_rules", "validate_rules")
    builder.add_edge("validate_rules", "detect_conflicts")

    def conflict_route(state):
        conflicts = deps.rule_service.repository.get_conflicts(state.get("conflict_ids", []))
        return "BLOCKING" if any(c.blocking for c in conflicts) else "CLEAR"
    builder.add_conditional_edges("detect_conflicts", conflict_route, {"BLOCKING": "build_conflict_question", "CLEAR": "resolve_rule_set"})
    builder.add_edge("build_conflict_question", "conflict_interrupt")
    builder.add_edge("conflict_interrupt", "apply_conflict_resolution")
    builder.add_edge("apply_conflict_resolution", "load_task_requirements")
    builder.add_edge("resolve_rule_set", "compile_criteria")
    builder.add_edge("compile_criteria", "validate_criteria_node")
    builder.add_edge("validate_criteria_node", "persist_criteria_snapshot")
    builder.add_edge("persist_criteria_snapshot", END)
    return builder.compile(checkpointer=checkpointer)
