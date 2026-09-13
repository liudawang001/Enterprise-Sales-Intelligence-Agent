from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.exports.models import ExportStatus
from app.main import create_app
from app.settings.production import Settings

pytestmark = [pytest.mark.integration, pytest.mark.recovery]


def restored_settings() -> Settings:
    database_url = os.getenv("TEST_RESTORED_DATABASE_URL")
    export_dir = os.getenv("TEST_RESTORED_EXPORT_DIR")
    if not database_url or not export_dir:
        pytest.skip("restored database and export directory are not configured")
    return Settings(
        app_env="development",
        database_url=database_url,
        checkpoint_database_url=database_url,
        graph_checkpointer="postgres",
        redis_url="redis://127.0.0.1:6399/15",
        redis_socket_timeout_seconds=0.1,
        redis_socket_connect_timeout_seconds=0.1,
        export_dir=export_dir,
    )


def test_restored_database_and_artifact_store_are_readable_through_api() -> None:
    app = create_app(restored_settings())

    with TestClient(app) as client:
        deps = app.state.dependencies
        completed = sorted(
            (
                item
                for item in deps.export_repository.jobs.values()
                if item.status == ExportStatus.COMPLETED and deps.export_service.storage.exists(item.export_id)
            ),
            key=lambda item: item.completed_at or item.created_at,
            reverse=True,
        )
        assert completed, "no restored export metadata has a matching restored artifact"
        export = completed[0]

        task = client.get(f"/api/tasks/{export.task_id}")
        assert task.status_code == 200
        leads = client.get(f"/api/tasks/{export.task_id}/versions/{export.task_version}/leads")
        assert leads.status_code == 200
        assert leads.json()["total"] > 0
        enterprise_id = leads.json()["items"][0]["enterprise_id"]

        evidence = client.get(
            f"/api/enterprises/{enterprise_id}/evidence",
            params={"task_id": export.task_id, "version": export.task_version},
        )
        assert evidence.status_code == 200
        assert evidence.json()["count"] > 0
        score = client.get(f"/api/tasks/{export.task_id}/versions/{export.task_version}/leads/{enterprise_id}/score")
        assert score.status_code == 200
        metadata = client.get(f"/api/exports/{export.export_id}")
        assert metadata.status_code == 200
        assert metadata.json()["sha256"] == export.sha256
        download = client.get(f"/api/exports/{export.export_id}/download")
        assert download.status_code == 200
        assert download.headers["x-artifact-sha256"] == export.sha256
        assert len(download.content) == export.file_size


def test_waiting_task_from_backup_resumes_against_restored_database() -> None:
    session_id = os.getenv("TEST_RESTORED_RESUME_SESSION_ID")
    expected_task_id = os.getenv("TEST_RESTORED_RESUME_TASK_ID")
    if not session_id or not expected_task_id:
        pytest.skip("restored resume identifiers are not configured")

    app = create_app(restored_settings())
    with TestClient(app) as client:
        before = client.get(f"/api/tasks/{expected_task_id}")
        assert before.status_code == 200
        resumed = client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "request_id": "fa001-restored-resume-complete-20260913",
                "message": "上海松江，3家",
            },
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "COMPLETED"
        assert resumed.json()["task_id"] == expected_task_id
        assert app.state.dependencies.research_service.repository.get_run_for_task(expected_task_id)
        assert app.state.dependencies.lead_score_repository.list_for_task(expected_task_id)
