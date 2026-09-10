from fastapi.testclient import TestClient

from app.main import create_app


def test_marketing_rule_crud_and_criteria_explain():
    app = create_app()
    client = TestClient(app)
    initial = client.get("/api/businesses/GROUP_VNET/marketing-rules")
    assert initial.status_code == 200 and initial.json()
    created = client.post("/api/businesses/GROUP_VNET/marketing-rules", json={"field": "industry", "operator": "EQ", "value": "制造业", "constraint_type": "SOFT", "weight": 0.5, "rationale": "Demo preference"})
    assert created.status_code == 200
    disabled = client.patch(f"/api/marketing-rules/{created.json()['rule_id']}/disable")
    assert disabled.status_code == 200 and disabled.json()["status"] == "DISABLED"

    response = client.post("/api/chat", json={"session_id": "criteria-api", "message": "帮我找上海松江50家集团V网企业，制造业优先"})
    task_id = response.json()["task_id"]
    criteria = client.get(f"/api/tasks/{task_id}/criteria")
    assert criteria.status_code == 200
    assert criteria.json()["criteria_hash"]
    assert criteria.json()["sources"]


def test_criteria_question_distinguishes_marketing_from_official():
    client = TestClient(create_app())
    client.post("/api/chat", json={"session_id": "explain-source", "message": "帮我找上海松江10家集团V网企业"})
    answer = client.post("/api/chat", json={"session_id": "explain-source", "message": "为什么多个办公地点是筛选条件？"}).json()
    assert "Demo Marketing Rule" in answer["message"]
    assert "不是当前知识库证明的官方办理要求" in answer["message"]
