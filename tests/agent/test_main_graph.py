from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


def test_main_graph_e2e_mock_flow():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    result = graph.invoke(
        {"session_id": "e2e-1", "incoming_text": "帮我找上海松江50家适合集团V网的企业"},
        config={"configurable": {"thread_id": "e2e-1"}},
    )
    assert result["task_status"] == "COMPLETED"
    assert len(result["lead_results"]) > 0
    assert result["criteria_snapshot_id"]
    assert result["candidate_count"] == 5


def test_thread_and_task_ids_are_distinct():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    graph.invoke(
        {"session_id": "id-1", "incoming_text": "帮我找上海松江50家集团V网客户"},
        config={"configurable": {"thread_id": "id-1"}},
    )
    task = deps.task_repository.get_active_task("id-1")
    assert task is not None
    assert task.task_id != "id-1"
