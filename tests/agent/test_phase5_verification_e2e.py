import pytest

from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


@pytest.mark.asyncio
async def test_research_verification_scoring_trace_is_complete():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    result = await graph.ainvoke(
        {
            "session_id": "phase5-e2e",
            "incoming_text": "帮我找上海松江3家适合集团V网的企业",
        },
        config={"configurable": {"thread_id": "phase5-e2e"}},
    )
    assert result["resolution_run_id"]
    assert result["verification_run_id"]
    assert result["verified_count"] == 3
    assert result["lead_set_id"]
    assert len(result["lead_results"]) == 3

    lead = result["lead_results"][0]
    score = deps.lead_score_repository.get_for_enterprise(lead["enterprise_id"])
    profile = deps.evidence_repository.get_profile(lead["enterprise_id"])
    assert score and profile
    evidence_ids = {
        evidence_id
        for component in score.component_scores
        for evidence_id in component.evidence_ids
    }
    assert evidence_ids
    for evidence_id in evidence_ids:
        evidence = deps.evidence_repository.evidence[evidence_id]
        assert evidence.source_record_id in deps.research_service.repository.sources
    reason = deps.lead_score_repository.reasons[lead["enterprise_id"]]
    assert set(reason.evidence_ids) <= evidence_ids


def test_verification_graph_has_required_nodes_and_bounded_router():
    deps = build_dependencies()
    graph = build_main_graph(deps).get_graph(xray=True)
    node_ids = set(graph.nodes)
    assert {
        "verification:load_candidate_set",
        "verification:build_resolution_groups",
        "verification:resolve_entities",
        "verification:collect_evidence",
        "verification:normalize_evidence",
        "verification:detect_field_conflicts",
        "verification:resolve_fields",
        "verification:targeted_verification",
        "verification:build_verified_profiles",
    } <= node_ids
