from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


def _invoke(graph, thread_id: str, text: str):
    return graph.invoke(
        {"session_id": thread_id, "incoming_text": text},
        config={"configurable": {"thread_id": thread_id}},
    )


def test_export_request_creates_artifact_without_business_reexecution():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    _invoke(graph, "graph-export", "帮我找上海松江3家集团V网企业")
    calls = len(deps.research_service.repository.tool_runs)
    scores = len(deps.lead_score_repository.scores)
    evidence = len(deps.evidence_repository.evidence)

    result = _invoke(graph, "graph-export", "导出刚才3家公司")

    assert result["export_id"]
    assert result["artifact_ref"] == result["export_id"]
    assert result["progress"]["event"] == "EXPORT_COMPLETED"
    assert len(deps.research_service.repository.tool_runs) == calls
    assert len(deps.lead_score_repository.scores) == scores
    assert len(deps.evidence_repository.evidence) == evidence


def test_export_request_reports_missing_field_without_searching():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    _invoke(graph, "graph-export-missing", "帮我找上海松江3家集团V网企业")
    calls = len(deps.research_service.repository.tool_runs)

    result = _invoke(graph, "graph-export-missing", "导出母公司")

    assert result["progress"]["event"] == "EXPORT_FAILED"
    assert result["progress"]["error_code"] == "EXPORT_FIELD_DATA_INCOMPLETE"
    assert len(deps.research_service.repository.tool_runs) == calls
