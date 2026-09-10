from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.main import create_app


def _chinese_pdf() -> bytes:
    font = "/System/Library/Fonts/Hiragino Sans GB.ttc"
    document = fitz.open()
    page = document.new_page()
    page.insert_font(fontname="zh", fontfile=font)
    page.insert_text((72, 72), "集团V网主要面向具有企业内部通信需求的集团客户。", fontname="zh", fontsize=12)
    return document.tobytes()


def test_upload_then_business_qa_returns_grounded_citation(tmp_path: Path) -> None:
    app = create_app()
    app.state.ingestion_service.storage.root = tmp_path
    client = TestClient(app)
    upload = client.post(
        "/api/documents",
        files={"file": ("demo_group_vnet.pdf", _chinese_pdf(), "application/pdf")},
        data={"title": "集团V网 Demo 业务说明", "business": "集团V网", "region": "NATIONAL", "authority": "DEMO"},
    )
    assert upload.status_code == 200
    assert upload.json()["status"] == "READY"
    assert upload.json()["chunk_count"] >= 1

    response = client.post("/api/chat", json={"session_id": "rag-e2e", "message": "集团V网主要面向什么客户？"})
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert "[1]" in body["message"]
    assert body["data"]["citations"][0]["document_title"] == "集团V网 Demo 业务说明"
    assert body["data"]["citations"][0]["page_start"] == 1
