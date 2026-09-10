from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.agent.subgraphs.business_qa.nodes import analyze_query, answer_grounded, answer_no_evidence, evidence_gate, retrieve_hybrid
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.services.knowledge_service import KnowledgeService


def build_business_qa_graph(service: KnowledgeService | None = None):
    rag_service = service or KnowledgeService(InMemoryKnowledgeRepository())
    builder = StateGraph(AgentState)
    builder.add_node("analyze_query", lambda state: analyze_query(state, rag_service))
    builder.add_node("retrieve_hybrid", lambda state: retrieve_hybrid(state, rag_service))
    builder.add_node("evidence_gate", evidence_gate)
    builder.add_node("answer_grounded", lambda state: answer_grounded(state, rag_service))
    builder.add_node("answer_no_evidence", answer_no_evidence)
    builder.add_edge(START, "analyze_query")
    builder.add_edge("analyze_query", "retrieve_hybrid")
    builder.add_edge("retrieve_hybrid", "evidence_gate")
    builder.add_conditional_edges("evidence_gate", lambda state: state.get("evidence_status", "INSUFFICIENT"), {"ENOUGH": "answer_grounded", "INSUFFICIENT": "answer_no_evidence"})
    builder.add_edge("answer_grounded", END)
    builder.add_edge("answer_no_evidence", END)
    return builder.compile()
