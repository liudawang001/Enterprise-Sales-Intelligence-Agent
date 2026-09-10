from app.agent.state import AgentState
from app.knowledge.services.knowledge_service import KnowledgeService


def analyze_query(state: AgentState, service: KnowledgeService) -> dict:
    query = service.analyze_query(state.get("incoming_text", ""))
    return {"knowledge_query": query.model_dump()}


def retrieve_hybrid(state: AgentState, service: KnowledgeService) -> dict:
    from app.knowledge.models import KnowledgeQuery
    query = KnowledgeQuery.model_validate(state.get("knowledge_query", {}))
    hits, warnings = service.retrieve(query)
    summaries = [{"chunk_id": hit.chunk_id, "document_id": hit.document_id, "fusion_score": hit.fusion_score, "page_start": hit.page_start, "page_end": hit.page_end} for hit in hits]
    return {"retrieval_hit_summaries": summaries, "evidence_count": len(hits), "rag_warnings": warnings}


def evidence_gate(state: AgentState) -> dict:
    count = state.get("evidence_count", 0)
    return {"evidence_status": "ENOUGH" if count else "INSUFFICIENT"}


def answer_grounded(state: AgentState, service: KnowledgeService) -> dict:
    from app.knowledge.models import KnowledgeQuery
    query = KnowledgeQuery.model_validate(state.get("knowledge_query", {}))
    result = service.answer(state.get("incoming_text", ""), query)
    return {"response_text": result["answer"], "citations": result["citations"], "rag_warnings": result["warnings"]}


def answer_no_evidence(state: AgentState) -> dict:
    return {"response_text": "当前知识库中没有找到足够证据确认该问题。", "citations": [], "rag_warnings": ["NO_EVIDENCE"]}
