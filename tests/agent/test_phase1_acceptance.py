from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


def test_complete_discovery_then_modify_target_count() -> None:
    deps = build_dependencies()
    graph = build_main_graph(deps)
    session_id = "acceptance-discovery"
    config = {"configurable": {"thread_id": session_id}}

    completed = graph.invoke(
        {
            "session_id": session_id,
            "incoming_text": "帮我找上海松江50家适合集团V网的企业",
        },
        config=config,
    )
    task_id = completed["active_task_id"]
    modified = graph.invoke(
        {"session_id": session_id, "incoming_text": "数量改成30家"},
        config=config,
    )
    task = deps.task_repository.get_active_task(session_id)

    assert completed["task_status"] == "COMPLETED"
    assert completed["candidate_count"] == 5
    assert len(completed["lead_results"]) == 5
    assert modified["intent"] == "TASK_MODIFICATION"
    assert modified["mutation_scope"] == "DISPLAY_ONLY"
    assert task is not None
    assert task.task_id == task_id
    assert task.task_id != session_id
    assert task.target_count == 30


def test_business_qa_stays_outside_lead_task_flow() -> None:
    deps = build_dependencies()
    graph = build_main_graph(deps)
    session_id = "acceptance-qa"
    result = graph.invoke(
        {"session_id": session_id, "incoming_text": "集团V网是什么？"},
        config={"configurable": {"thread_id": session_id}},
    )

    assert result["intent"] == "BUSINESS_QA"
    assert "Mock Answer" in result["response_text"]
    assert deps.task_repository.get_active_task(session_id) is None
