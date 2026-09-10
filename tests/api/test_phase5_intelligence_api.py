from fastapi.testclient import TestClient

from app.main import create_app


def test_entity_evidence_verification_score_and_explain_apis():
    client = TestClient(create_app())
    response = client.post(
        "/api/chat",
        json={
            "session_id": "api-phase5",
            "message": "帮我找上海松江3家适合集团V网的企业",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    task_id = payload["task_id"]
    enterprise_id = payload["data"]["lead_results"][0]["enterprise_id"]

    verification = client.get(f"/api/tasks/{task_id}/verification")
    enterprise = client.get(f"/api/enterprises/{enterprise_id}")
    relations = client.get(f"/api/enterprises/{enterprise_id}/relations")
    evidence = client.get(f"/api/enterprises/{enterprise_id}/evidence")
    field_evidence = client.get(
        f"/api/enterprises/{enterprise_id}/fields/legal_name/evidence"
    )
    scores = client.get(f"/api/tasks/{task_id}/scores")
    score = client.get(f"/api/leads/{enterprise_id}/score")
    explanation = client.get(f"/api/leads/{enterprise_id}/score/explain")

    assert verification.status_code == enterprise.status_code == 200
    assert verification.json()["status"] == "COMPLETED"
    assert enterprise.json()["verified_profile"]
    assert relations.json()["count"] >= 0
    assert evidence.json()["count"] > 0
    assert field_evidence.json()["field"]["supporting_evidence_ids"]
    assert scores.json()["count"] == 3
    assert score.json()["component_scores"]
    assert set(explanation.json()["evidence_ids"]) <= {
        evidence_id
        for component in score.json()["component_scores"]
        for evidence_id in component["evidence_ids"]
    }
