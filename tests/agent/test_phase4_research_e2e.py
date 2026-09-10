import pytest

from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


@pytest.mark.asyncio
async def test_provider_driven_research_graph_persists_plan_lineage_and_sources():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    result = await graph.ainvoke(
        {"session_id": "phase4", "incoming_text": "帮我找上海松江3家适合集团V网的企业"},
        config={"configurable": {"thread_id": "phase4"}},
    )
    repository = deps.research_service.repository
    run = repository.runs[result["research_run_id"]]
    plan = repository.plans[result["search_plan_id"]]
    final_set = repository.candidate_sets[result["candidate_set_id"]]
    assert run.status == "COMPLETED"
    assert final_set.parent_set_id == run.filtered_candidate_set_id
    assert final_set.criteria_snapshot_id == result["criteria_snapshot_id"]
    assert plan.pushdown_explain["enterprise"]["provider_filters"]
    assert len(result["lead_results"]) == 3
    assert all(repository.get_sources(cid) for cid in final_set.candidate_ids)
    assert len(repository.tool_runs) > 0


@pytest.mark.asyncio
async def test_insufficient_candidates_expands_only_to_configured_round_limit():
    deps = build_dependencies()
    result = await build_main_graph(deps).ainvoke(
        {
            "session_id": "phase4-partial",
            "incoming_text": "帮我找上海松江50家适合集团V网的企业",
        },
        config={"configurable": {"thread_id": "phase4-partial"}},
    )
    run = deps.research_service.repository.runs[result["research_run_id"]]
    assert result["expansion_round"] == 2
    assert run.status == "PARTIAL" and run.error_code == "INSUFFICIENT_CANDIDATES"
    assert result["candidate_count"] == 5
