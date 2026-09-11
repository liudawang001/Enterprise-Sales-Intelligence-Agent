from fastapi.testclient import TestClient

from app.main import create_app


def _completed_task(client: TestClient, session_id: str = "delivery-api") -> dict:
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "帮我找上海松江3家集团V网企业"},
    )
    assert response.status_code == 200
    return response.json()


def test_versioned_lead_list_detail_evidence_and_score():
    client = TestClient(create_app())
    completed = _completed_task(client)
    task_id = completed["task_id"]
    version = client.get(f"/api/tasks/{task_id}").json()["task"]["version"]

    page = client.get(
        f"/api/tasks/{task_id}/versions/{version}/leads",
        params={"page": 1, "page_size": 2, "sort_by": "rank"},
    )
    assert page.status_code == 200
    payload = page.json()
    assert payload["total"] == 3
    assert [item["rank"] for item in payload["items"]] == [1, 2]
    assert payload["snapshot_id"]
    enterprise_id = payload["items"][0]["enterprise_id"]

    detail = client.get(
        f"/api/tasks/{task_id}/versions/{version}/leads/{enterprise_id}"
    )
    score = client.get(
        f"/api/tasks/{task_id}/versions/{version}/leads/{enterprise_id}/score"
    )
    evidence = client.get(
        f"/api/enterprises/{enterprise_id}/evidence",
        params={"snapshot_id": payload["snapshot_id"]},
    )

    assert detail.status_code == score.status_code == evidence.status_code == 200
    assert detail.json()["snapshot_id"] == payload["snapshot_id"]
    assert score.json()["task_version"] == version
    assert evidence.json()["snapshot_id"] == payload["snapshot_id"]


def test_delivery_filters_are_server_side_and_page_size_is_bounded():
    client = TestClient(create_app())
    completed = _completed_task(client, "delivery-filter")
    task_id = completed["task_id"]
    version = client.get(f"/api/tasks/{task_id}").json()["task"]["version"]

    first = client.get(
        f"/api/tasks/{task_id}/versions/{version}/leads",
        params={"page": 1, "page_size": 1},
    ).json()
    second = client.get(
        f"/api/tasks/{task_id}/versions/{version}/leads",
        params={"page": 2, "page_size": 1},
    ).json()
    too_large = client.get(
        f"/api/tasks/{task_id}/versions/{version}/leads",
        params={"page_size": 101},
    )

    assert first["items"][0]["enterprise_id"] != second["items"][0]["enterprise_id"]
    assert second["items"][0]["rank"] == 2
    assert too_large.status_code == 422


def test_task_sse_finishes_with_terminal_event_and_status_recovers_state():
    client = TestClient(create_app())
    completed = _completed_task(client, "delivery-sse")
    task_id = completed["task_id"]

    stream = client.get(f"/api/tasks/{task_id}/events/stream")
    status = client.get(f"/api/tasks/{task_id}/events")

    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert '"event": "FINAL"' in stream.text
    assert '"status": "COMPLETED"' in stream.text
    assert status.json()["status"] == "COMPLETED"
    assert status.json()["progress"]["event"] == "FINAL"
