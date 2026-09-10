from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.agent.subgraphs.research.nodes import (
    dispatch_cheap_enrichment,
    dispatch_deep_research,
    dispatch_discovery,
    make_apply_hard_filters,
    make_build_search_plan,
    make_expand_search_plan,
    make_load_criteria,
    make_merge_discovery,
    make_persist_cheap_enriched_set,
    make_persist_researched_set,
    make_route_more_candidates,
    make_run_deep_research_batch,
    make_run_discovery_batch,
    make_run_enrichment_batch,
    make_select_deep_research,
    normalize_candidates,
    persist_raw_candidate_set,
    persist_search_plan,
    validate_search_plan,
)


def build_research_graph(deps: AgentDependencies):
    builder = StateGraph(AgentState)
    builder.add_node("load_criteria", make_load_criteria(deps))
    builder.add_node("build_search_plan", make_build_search_plan(deps))
    builder.add_node("validate_search_plan", validate_search_plan)
    builder.add_node("persist_search_plan", persist_search_plan)
    builder.add_node("dispatch_discovery", dispatch_discovery)
    builder.add_node("run_discovery_batch", make_run_discovery_batch(deps))
    builder.add_node("merge_discovery", make_merge_discovery(deps))
    builder.add_node("normalize_candidates", normalize_candidates)
    builder.add_node("persist_raw_candidate_set", persist_raw_candidate_set)
    builder.add_node("expand_search_plan", make_expand_search_plan(deps))
    builder.add_node("dispatch_cheap_enrichment", dispatch_cheap_enrichment)
    builder.add_node("run_cheap_enrichment_batch", make_run_enrichment_batch(deps))
    builder.add_node(
        "persist_cheap_enriched_set", make_persist_cheap_enriched_set(deps)
    )
    builder.add_node("apply_hard_filters", make_apply_hard_filters(deps))
    builder.add_node("select_deep_research", make_select_deep_research(deps))
    builder.add_node("dispatch_deep_research", dispatch_deep_research)
    builder.add_node("run_deep_research_batch", make_run_deep_research_batch(deps))
    builder.add_node(
        "persist_researched_candidate_set", make_persist_researched_set(deps)
    )

    builder.add_edge(START, "load_criteria")
    builder.add_edge("load_criteria", "build_search_plan")
    builder.add_edge("build_search_plan", "validate_search_plan")
    builder.add_edge("validate_search_plan", "persist_search_plan")
    builder.add_edge("persist_search_plan", "dispatch_discovery")
    builder.add_conditional_edges(
        "dispatch_discovery",
        lambda state: [
            Send(
                "run_discovery_batch",
                {"research_run_id": state["research_run_id"], "discovery_batch": batch},
            )
            for batch in state.get("discovery_batches", [])
        ],
    )
    builder.add_edge("run_discovery_batch", "merge_discovery")
    builder.add_edge("merge_discovery", "normalize_candidates")
    builder.add_edge("normalize_candidates", "persist_raw_candidate_set")
    builder.add_conditional_edges(
        "persist_raw_candidate_set",
        make_route_more_candidates(deps),
        {"EXPAND": "expand_search_plan", "CONTINUE": "dispatch_cheap_enrichment"},
    )
    builder.add_edge("expand_search_plan", "dispatch_discovery")
    builder.add_conditional_edges(
        "dispatch_cheap_enrichment",
        lambda state: [
            Send(
                "run_cheap_enrichment_batch",
                {
                    "research_run_id": state["research_run_id"],
                    "enrichment_batch": batch,
                },
            )
            for batch in state.get("enrichment_batches", [])
        ],
    )
    builder.add_edge("run_cheap_enrichment_batch", "persist_cheap_enriched_set")
    builder.add_edge("persist_cheap_enriched_set", "apply_hard_filters")
    builder.add_edge("apply_hard_filters", "select_deep_research")
    builder.add_edge("select_deep_research", "dispatch_deep_research")
    builder.add_conditional_edges(
        "dispatch_deep_research",
        lambda state: [
            Send(
                "run_deep_research_batch",
                {
                    "research_run_id": state["research_run_id"],
                    "deep_research_batch": batch,
                },
            )
            for batch in state.get("deep_research_batches", [])
        ],
    )
    builder.add_edge("run_deep_research_batch", "persist_researched_candidate_set")
    builder.add_edge("persist_researched_candidate_set", END)
    return builder.compile()
