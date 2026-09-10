from app.knowledge.enums import DocumentAuthority, DocumentStatus
from app.knowledge.ingestion.tokenizer import JiebaLexicalTokenizer
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.main import create_app
from fastapi.testclient import TestClient


def test_rule_conflict_interrupt_and_resume_end_to_end():
    app = create_app()
    document = KnowledgeDocument(title="集团V网 Demo 规则", original_filename="demo.pdf", file_hash="phase3-conflict", business="集团V网", region="NATIONAL", authority=DocumentAuthority.DEMO, status=DocumentStatus.READY, file_path="demo.pdf", page_count=1, chunk_count=1)
    app.state.knowledge_repository.create_document(document)
    content = "集团V网办理原则上成员数量不少于10。"
    chunk = KnowledgeChunk(document_id=document.id, chunk_index=0, content=content, lexical_content=JiebaLexicalTokenizer().tokenize(content), page_start=1, page_end=1, content_hash="phase3-conflict-chunk")
    chunk.embedding = app.state.knowledge_service.embedding.embed_documents([content])[0]
    app.state.knowledge_repository.replace_chunks(document.id, [chunk])
    client = TestClient(app)

    first = client.post("/api/chat", json={"session_id": "rule-conflict", "message": "帮我找上海松江50家集团V网企业，成员数少于5"}).json()
    assert first["status"] == "WAITING_USER"
    assert first["interrupt"]["type"] == "RULE_CONFLICT"
    assert first["interrupt"]["conflicts"][0]["blocking"] is True

    resumed = client.post("/api/chat", json={"session_id": "rule-conflict", "message": "那就按官方条件，至少10人"}).json()
    assert resumed["status"] == "COMPLETED"
    assert resumed["data"]["criteria_snapshot_id"]
    assert resumed["data"]["lead_results"]

