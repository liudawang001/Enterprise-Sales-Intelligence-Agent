from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph
from app.agent.routers.intent_router import route_intent
from app.agent.nodes.intent import classify_intent


def test_classifies_required_intents():
    cases = {
        "集团V网是什么？": "BUSINESS_QA",
        "帮我找集团V网客户": "LEAD_DISCOVERY",
        "导出Excel": "EXPORT_REQUEST",
        "为什么第一家公司评分最高？": "LEAD_QUERY",
        "你好": "GENERAL_CHAT",
    }
    for text, expected in cases.items():
        state = classify_intent({"incoming_text": text})
        assert route_intent(state) == expected

    mutation = classify_intent({"incoming_text": "数量改成30家", "active_task_id": "task-1"})
    assert route_intent(mutation) == "TASK_MODIFICATION"


def test_business_qa_does_not_create_task():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    config = {"configurable": {"thread_id": "qa-1"}}
    result = graph.invoke({"session_id": "qa-1", "incoming_text": "集团V网是什么？"}, config=config)
    assert result["intent"] == "BUSINESS_QA"
    assert result["active_task_id"] is None
    assert deps.task_repository.get_active_task("qa-1") is None
