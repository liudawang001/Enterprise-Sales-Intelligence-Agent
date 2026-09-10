from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


def test_soft_mutation_creates_new_criteria_and_diff():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    config = {"configurable": {"thread_id": "phase3-mutation"}}
    first = graph.invoke({"session_id": "phase3-mutation", "incoming_text": "帮我找上海松江50家集团V网企业"}, config=config)
    second = graph.invoke({"session_id": "phase3-mutation", "incoming_text": "制造业优先"}, config=config)
    assert second["mutation_scope"] == "RANK_ONLY"
    assert second["criteria_snapshot_id"] != first["criteria_snapshot_id"]
    assert second["criteria_diff"]["added_soft"]


def test_business_mutation_is_full_replan():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    config = {"configurable": {"thread_id": "phase3-business-mutation"}}
    graph.invoke({"session_id": "phase3-business-mutation", "incoming_text": "帮我找上海松江10家集团V网企业"}, config=config)
    result = graph.invoke({"session_id": "phase3-business-mutation", "incoming_text": "集团V网不做了，改成企业专线"}, config=config)
    assert result["mutation_scope"] == "FULL_REPLAN"
    assert result["criteria_diff"]["business_changed"] is True

