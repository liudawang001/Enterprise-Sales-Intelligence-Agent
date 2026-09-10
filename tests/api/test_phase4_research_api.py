from fastapi.testclient import TestClient

from app.main import create_app


def test_research_candidate_source_plan_and_progress_apis():
    client = TestClient(create_app())
    response = client.post(
        "/api/chat",
        json={"session_id": "api-p4", "message": "帮我找上海松江3家适合集团V网的企业"},
    )
    assert response.status_code == 200
    payload = response.json()
    task_id, run_id = payload["task_id"], payload["data"]["research_run_id"]
    research = client.get(f"/api/tasks/{task_id}/research")
    candidates = client.get(f"/api/tasks/{task_id}/candidates")
    plan = client.get(f"/api/research/{run_id}/plan")
    events = client.get(f"/api/research/{run_id}/events")
    assert research.json()["status"] == "COMPLETED"
    assert candidates.json()["count"] == 3
    candidate = candidates.json()["items"][0]
    assert candidate["provisional"] is True and candidate["source_count"] >= 1
    assert (
        client.get(f"/api/candidates/{candidate['candidate_id']}/sources").json()[
            "count"
        ]
        >= 1
    )
    assert "pushdown_explain" in plan.json()["plan"]
    assert "RESEARCH_COMPLETED" in events.text
