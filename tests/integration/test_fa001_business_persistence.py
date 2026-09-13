from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.postgres_business import (
    PostgresDeliverySnapshotRepository,
    PostgresEnterpriseRepository,
    PostgresEvidenceRepository,
    PostgresExecutionSnapshotRepository,
    PostgresExportRepository,
    PostgresLeadScoreRepository,
    PostgresMutationRepository,
    PostgresResearchRepository,
    PostgresRuleRepository,
    PostgresTaskRepository,
)
from app.settings.production import Settings

pytestmark = pytest.mark.integration


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return value


def settings(database_url: str, export_dir: str) -> Settings:
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


def test_full_business_state_survives_fresh_application(tmp_path) -> None:
    config = settings(database_url(), str(tmp_path / "exports"))
    session_id = f"fa001-{uuid4()}"
    request_id = f"request-{uuid4()}"

    app_a = create_app(config)
    with TestClient(app_a) as client:
        deps = app_a.state.dependencies
        assert isinstance(deps.task_repository, PostgresTaskRepository)
        assert isinstance(deps.rule_service.repository, PostgresRuleRepository)
        assert isinstance(deps.research_service.repository, PostgresResearchRepository)
        assert isinstance(deps.enterprise_repository, PostgresEnterpriseRepository)
        assert isinstance(deps.evidence_repository, PostgresEvidenceRepository)
        assert isinstance(deps.lead_score_repository, PostgresLeadScoreRepository)
        assert isinstance(deps.mutation_repository, PostgresMutationRepository)
        assert isinstance(deps.execution_snapshot_repository, PostgresExecutionSnapshotRepository)
        assert isinstance(deps.delivery_snapshot_repository, PostgresDeliverySnapshotRepository)
        assert isinstance(deps.export_repository, PostgresExportRepository)

        response = client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "request_id": request_id,
                "message": "帮我找上海松江3家适合集团V网的企业，制造业优先",
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "COMPLETED"
        task_id = result["task_id"]
        task = deps.task_repository.get_task(task_id)
        assert task is not None
        bundle = deps.delivery_query_service.freeze(task_id, task.version)
        assert bundle.leads

        export = client.post(
            "/api/exports",
            json={
                "task_id": task_id,
                "task_version": task.version,
                "snapshot_id": bundle.snapshot.snapshot_id,
                "target_count": len(bundle.leads),
                "fields": [
                    "rank",
                    "enterprise_id",
                    "enterprise_name",
                    "lead_score",
                    "verification_status",
                ],
            },
        )
        assert export.status_code == 200, export.text
        export_id = export.json()["export_id"]
        version = task.version
        snapshot_id = bundle.snapshot.snapshot_id
        enterprise_ids = [item.enterprise_id for item in bundle.leads]

    # A new FastAPI app creates a completely new dependency graph and repository cache.
    app_b = create_app(config)
    with TestClient(app_b) as client:
        deps = app_b.state.dependencies
        task = deps.task_repository.get_task(task_id)
        assert task is not None and task.version == version

        research = deps.research_service.repository.get_run_for_task(task_id)
        assert research is not None and research.researched_candidate_set_id
        candidates = deps.research_service.repository.get_candidates(research.researched_candidate_set_id)
        assert candidates
        assert any(deps.research_service.repository.get_sources(item.candidate_id) for item in candidates)

        assert deps.enterprise_repository.list_for_task(task_id)
        assert all(deps.evidence_repository.list_evidence(item) for item in enterprise_ids)
        assert all(deps.evidence_repository.get_profile(item) for item in enterprise_ids)
        assert deps.lead_score_repository.list_for_task(task_id)
        assert deps.execution_snapshot_repository.for_version(task_id, version)
        assert deps.delivery_snapshot_repository.get(snapshot_id)
        assert deps.export_repository.get(export_id, "local")

        leads = client.get(f"/api/tasks/{task_id}/versions/{version}/leads")
        assert leads.status_code == 200 and leads.json()["total"] == len(enterprise_ids)
        evidence = client.get(
            f"/api/enterprises/{enterprise_ids[0]}/evidence",
            params={"task_id": task_id, "version": version},
        )
        assert evidence.status_code == 200 and evidence.json()["count"] > 0
        score = client.get(f"/api/tasks/{task_id}/versions/{version}/leads/{enterprise_ids[0]}/score")
        assert score.status_code == 200
        metadata = client.get(f"/api/exports/{export_id}")
        assert metadata.status_code == 200 and metadata.json()["status"] == "COMPLETED"
        download = client.get(f"/api/exports/{export_id}/download")
        assert download.status_code == 200


@pytest.mark.recovery
def test_interrupted_business_flow_resumes_in_fresh_application(tmp_path) -> None:
    config = settings(database_url(), str(tmp_path / "exports"))
    session_id = f"fa001-resume-{uuid4()}"

    app_a = create_app(config)
    with TestClient(app_a) as client:
        first = client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "request_id": f"request-{uuid4()}",
                "message": "帮我找集团V网客户",
            },
        )
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "WAITING_USER"
        assert first.json()["interrupt"]["missing_slots"] == ["region", "target_count"]
        task_id = first.json()["task_id"]

    app_b = create_app(config)
    with TestClient(app_b) as client:
        persisted_task = app_b.state.dependencies.task_repository.get_task(task_id)
        assert persisted_task is not None
        resumed = client.post(
            "/api/chat",
            json={
                "session_id": session_id,
                "request_id": f"request-{uuid4()}",
                "message": "上海松江，3家",
            },
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "COMPLETED"
        assert resumed.json()["task_id"] == task_id
        completed_task = app_b.state.dependencies.task_repository.get_task(task_id)
        assert completed_task is not None
        assert completed_task.status.value == "COMPLETED"
        assert app_b.state.dependencies.research_service.repository.get_run_for_task(task_id)
        assert app_b.state.dependencies.lead_score_repository.list_for_task(task_id)
