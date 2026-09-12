from fastapi.testclient import TestClient

from app.exports.models import ExportJob, ExportStatus
from app.knowledge.enums import DocumentStatus
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeFilter
from app.main import create_app
from app.observability.context import RequestContext, reset_request_context, set_request_context
from app.security.principal import Principal, Role


def test_cross_workspace_task_is_not_disclosed() -> None:
    app = create_app()
    token = set_request_context(
        RequestContext(
            request_id="r",
            trace_id="t",
            principal=Principal(user_id="other", workspace_id="workspace-b", roles={Role.ANALYST}),
        )
    )
    try:
        hidden = app.state.dependencies.task_repository.create_task("private-thread", "message")
    finally:
        reset_request_context(token)
    response = TestClient(app).get(f"/api/tasks/{hidden.task_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "TASK_NOT_FOUND"


def test_cross_workspace_export_is_not_disclosed() -> None:
    app = create_app()
    export = ExportJob(
        snapshot_id="snapshot-b",
        task_id="task-b",
        workspace_id="workspace-b",
        task_version=1,
        status=ExportStatus.COMPLETED,
        requested_fields=["rank"],
        request_hash="hash-b",
    )
    app.state.dependencies.export_repository.save(export)
    response = TestClient(app).get(f"/api/exports/{export.export_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "EXPORT_NOT_FOUND"


def test_health_and_security_headers_are_available() -> None:
    response = TestClient(create_app()).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-trace-id"]


def test_workspace_knowledge_filter_never_returns_another_workspace_document() -> None:
    app = create_app()
    repository = app.state.knowledge_repository
    private = KnowledgeDocument(
        title="Private",
        original_filename="private.pdf",
        file_hash="private-hash",
        access_scope="WORKSPACE",
        workspace_id="workspace-b",
        status=DocumentStatus.READY,
        file_path="/tmp/private.pdf",
    )
    repository.create_document(private)
    repository.replace_chunks(
        private.id,
        [
            KnowledgeChunk(
                document_id=private.id,
                chunk_index=0,
                content="private",
                lexical_content="private",
                page_start=1,
                page_end=1,
                content_hash="chunk-hash",
            )
        ],
    )
    assert repository.list_chunks(knowledge_filter=KnowledgeFilter(workspace_id="workspace-a")) == []
    assert len(repository.list_chunks(knowledge_filter=KnowledgeFilter(workspace_id="workspace-b"))) == 1
