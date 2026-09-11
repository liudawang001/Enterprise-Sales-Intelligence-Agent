from fastapi.testclient import TestClient

from app.main import create_app


def test_create_status_history_and_download_existing_export():
    client = TestClient(create_app())
    created = client.post(
        "/api/chat",
        json={"session_id": "export-api", "message": "帮我找上海松江3家集团V网企业"},
    ).json()
    task_id = created["task_id"]
    version = client.get(f"/api/tasks/{task_id}").json()["task"]["version"]
    payload = {
        "task_id": task_id,
        "task_version": version,
        "fields": ["rank", "enterprise_name", "lead_score", "verification_status"],
    }
    exported = client.post("/api/exports", json=payload)
    assert exported.status_code == 200
    job = exported.json()
    assert job["status"] == "COMPLETED"

    status = client.get(f"/api/exports/{job['export_id']}")
    history = client.get(f"/api/tasks/{task_id}/exports")
    download = client.get(f"/api/exports/{job['export_id']}/download")

    assert status.json()["sha256"] == job["sha256"]
    assert history.json()["items"][0]["export_id"] == job["export_id"]
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert download.headers["x-artifact-sha256"] == job["sha256"]
    assert len(download.content) == job["file_size"]
    events = client.get(f"/api/exports/{job['export_id']}/events").json()
    assert [item["event"] for item in events["items"]] == [
        "EXPORT_STARTED",
        "EXPORT_COMPLETED",
    ]


def test_export_api_rejects_missing_requested_data_and_unknown_fields():
    app = create_app()
    client = TestClient(app)
    created = client.post(
        "/api/chat",
        json={"session_id": "export-invalid", "message": "帮我找上海松江3家集团V网企业"},
    ).json()
    task_id = created["task_id"]
    unknown = client.post(
        "/api/exports", json={"task_id": task_id, "fields": ["database_column"]}
    )
    missing = client.post(
        "/api/exports", json={"task_id": task_id, "fields": ["parent_enterprise"]}
    )
    assert unknown.status_code == 422
    assert "UNKNOWN_EXPORT_FIELD" in unknown.json()["detail"]
    assert missing.status_code == 422
    assert "EXPORT_FIELD_DATA_INCOMPLETE" in missing.json()["detail"]
