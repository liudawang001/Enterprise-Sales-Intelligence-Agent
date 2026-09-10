from datetime import date
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.knowledge.enums import DocumentAuthority

router = APIRouter(prefix="/api/documents", tags=["knowledge"])


@router.post("")
async def upload_document(request: Request, file: UploadFile = File(...), title: str = Form(...), business: str | None = Form(None), document_type: str | None = Form(None), region: str = Form("NATIONAL"), authority: DocumentAuthority = Form(DocumentAuthority.DEMO), version: str | None = Form(None), effective_from: date | None = Form(None), effective_to: date | None = Form(None)):
    result = await request.app.state.ingestion_service.ingest(filename=file.filename or "upload.pdf", content=await file.read(), title=title, business=business, document_type=document_type, region=region, authority=authority, version=version, effective_from=effective_from, effective_to=effective_to)
    payload = {"document_id": str(result.id), "status": result.status.value, "page_count": result.page_count, "chunk_count": result.chunk_count}
    if result.status.value == "FAILED":
        message = result.error_message or "Document ingestion failed"
        code = "UNSUPPORTED_SCANNED_PDF" if "UNSUPPORTED_SCANNED_PDF" in message else ("INVALID_DOCUMENT" if "Only valid PDF" in message else "PDF_PARSE_FAILED")
        payload["error"] = {"code": code, "message": message}
    return payload


@router.get("")
async def list_documents(request: Request):
    return [document.model_dump(mode="json") for document in request.app.state.knowledge_repository.list_documents()]


@router.get("/{document_id}")
async def get_document(document_id: UUID, request: Request):
    document = request.app.state.knowledge_repository.get_document(document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return document.model_dump(mode="json")


@router.post("/{document_id}/reindex")
async def reindex_document(document_id: UUID, request: Request):
    try:
        document = await request.app.state.ingestion_service.reindex(document_id)
    except KeyError:
        raise HTTPException(404, "Document not found") from None
    return document.model_dump(mode="json")


@router.post("/{document_id}/disable")
async def disable_document(document_id: UUID, request: Request):
    try:
        document = request.app.state.ingestion_service.disable(document_id)
    except KeyError:
        raise HTTPException(404, "Document not found") from None
    return document.model_dump(mode="json")
