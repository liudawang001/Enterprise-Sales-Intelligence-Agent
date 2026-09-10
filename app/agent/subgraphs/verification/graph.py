from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.agent.subgraphs.verification.nodes import (
    make_build_resolution_groups,
    make_build_verified_profiles,
    make_collect_evidence,
    make_detect_field_conflicts,
    make_load_candidate_set,
    make_resolve_entities,
    make_resolve_fields,
    make_targeted_verification,
    normalize_evidence,
    persist_canonical_entities,
)
from app.agent.subgraphs.verification.routers import route_more_evidence


def build_verification_graph(deps: AgentDependencies):
    builder = StateGraph(AgentState)
    builder.add_node("load_candidate_set", make_load_candidate_set(deps))
    builder.add_node("build_resolution_groups", make_build_resolution_groups(deps))
    builder.add_node("resolve_entities", make_resolve_entities(deps))
    builder.add_node("persist_canonical_entities", persist_canonical_entities)
    builder.add_node("collect_evidence", make_collect_evidence(deps))
    builder.add_node("normalize_evidence", normalize_evidence)
    builder.add_node("detect_field_conflicts", make_detect_field_conflicts(deps))
    builder.add_node("resolve_fields", make_resolve_fields(deps))
    builder.add_node("targeted_verification", make_targeted_verification(deps))
    builder.add_node("build_verified_profiles", make_build_verified_profiles(deps))
    builder.add_edge(START, "load_candidate_set")
    builder.add_edge("load_candidate_set", "build_resolution_groups")
    builder.add_edge("build_resolution_groups", "resolve_entities")
    builder.add_edge("resolve_entities", "persist_canonical_entities")
    builder.add_edge("persist_canonical_entities", "collect_evidence")
    builder.add_edge("collect_evidence", "normalize_evidence")
    builder.add_edge("normalize_evidence", "detect_field_conflicts")
    builder.add_edge("detect_field_conflicts", "resolve_fields")
    builder.add_conditional_edges("resolve_fields", route_more_evidence, {"TARGET": "targeted_verification", "BUILD": "build_verified_profiles"})
    builder.add_edge("targeted_verification", "collect_evidence")
    builder.add_edge("build_verified_profiles", END)
    return builder.compile()
