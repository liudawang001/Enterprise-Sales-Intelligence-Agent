from fastapi.testclient import TestClient

from app.main import create_app


def test_chat_api_interrupt_and_resume() -> None:
    client = TestClient(create_app())
    first = client.post("/api/chat", json={"session_id": "api-test", "message": "帮我找集团V网客户"})
    assert first.status_code == 200
    assert first.json()["status"] == "WAITING_USER"
    assert first.json()["interrupt"]["missing_slots"] == ["region", "target_count"]

    second = client.post("/api/chat", json={"session_id": "api-test", "message": "上海松江，50家"})
    assert second.status_code == 200
    assert second.json()["status"] == "COMPLETED"
    assert len(second.json()["data"]["lead_results"]) == 5


def test_chat_api_complete_request_and_business_qa() -> None:
    client = TestClient(create_app())
    complete = client.post(
        "/api/chat",
        json={"session_id": "api-complete", "message": "帮我找上海松江50家集团V网客户"},
    )
    qa = client.post("/api/chat", json={"session_id": "api-qa", "message": "集团V网是什么？"})

    assert complete.json()["status"] == "COMPLETED"
    assert complete.json()["task_id"] != "api-complete"
    assert qa.json()["task_id"] is None
    assert "没有找到足够证据" in qa.json()["message"]
