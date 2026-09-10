from fastapi.testclient import TestClient

from app.main import create_app


def test_task_version_mutation_and_explain_apis():
    app = create_app()
    client = TestClient(app)
    created = client.post("/api/chat", json={"session_id": "task-api", "message": "帮我找上海松江3家集团V网企业"}).json()
    task_id = created["task_id"]
    task = client.get(f"/api/tasks/{task_id}").json()["task"]

    response = client.post(
        f"/api/tasks/{task_id}/mutations",
        json={"base_version": task["version"], "source_message_id": "api-mutation-1", "patch": {"target_count": 2}},
    )
    assert response.status_code == 200
    mutation = response.json()
    detail = client.get(f"/api/tasks/{task_id}/mutations/{mutation['mutation_id']}")
    plan = client.get(f"/api/reexecution/{mutation['reexecution_plan_id']}")
    versions = client.get(f"/api/tasks/{task_id}/versions")

    assert mutation["scope"] == "DISPLAY_ONLY"
    assert detail.json()["reason_codes"] == ["TARGET_COUNT_DECREASE"]
    assert plan.json()["reused_artifact_ids"]
    assert plan.json()["target_version"] == 3
    assert len(versions.json()) == 3


def test_structured_mutation_rejects_stale_version_and_is_idempotent():
    app = create_app()
    client = TestClient(app)
    task_id = client.post("/api/chat", json={"session_id": "fence-api", "message": "帮我找上海松江3家集团V网企业"}).json()["task_id"]
    version = client.get(f"/api/tasks/{task_id}").json()["task"]["version"]
    payload = {"base_version": version, "source_message_id": "same-request", "patch": {"target_count": 2}}

    first = client.post(f"/api/tasks/{task_id}/mutations", json=payload)
    duplicate = client.post(f"/api/tasks/{task_id}/mutations", json=payload)
    stale = client.post(f"/api/tasks/{task_id}/mutations", json={"base_version": version, "source_message_id": "other-request", "patch": {"target_count": 1}})

    assert first.json() == duplicate.json()
    assert stale.status_code == 409


def test_task_list_version_detail_and_activation():
    app = create_app()
    client = TestClient(app)
    first = client.post("/api/chat", json={"session_id": "switch-api", "message": "帮我找上海松江2家集团V网企业"}).json()["task_id"]
    second = client.post("/api/chat", json={"session_id": "switch-api", "message": "再建一个上海浦东2家企业专线任务"}).json()["task_id"]

    tasks = client.get("/api/tasks", params={"session_id": "switch-api"}).json()
    version = client.get(f"/api/tasks/{first}/versions/2")
    activated = client.post(f"/api/tasks/{first}/activate", json={"session_id": "switch-api"})

    assert {item["task_id"] for item in tasks} == {first, second}
    assert version.status_code == 200
    assert activated.json() == {"task_id": first, "active": True, "version": 2}
