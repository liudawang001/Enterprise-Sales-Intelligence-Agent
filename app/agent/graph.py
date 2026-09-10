import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.enums import IntentType, MutationScope
from app.agent.nodes.context import load_context
from app.agent.nodes.intent import classify_intent
from app.agent.nodes.response import compose_lead_response
from app.agent.nodes.scoring import score_leads
from app.agent.nodes.task import create_lead_task
from app.agent.routers.intent_router import route_intent
from app.agent.routers.mutation_router import route_mutation
from app.agent.state import AgentState
from app.agent.subgraphs.business_planning.graph import build_business_planning_graph
from app.agent.subgraphs.business_qa.graph import build_business_qa_graph
from app.agent.subgraphs.mutation.graph import build_mutation_graph
from app.agent.subgraphs.research.graph import build_research_graph
from app.agent.subgraphs.requirement.graph import build_requirement_graph

logger = logging.getLogger(__name__)


def _response_node(text: str):
    def node(_state: AgentState) -> dict:
        return {"response_text": text}
    return node


def _lead_query_node(state: AgentState) -> dict:
    leads = state.get("lead_results", [])
    if not leads:
        return {"response_text": "当前还没有可解释的潜客评分结果。"}
    lead = leads[0]
    return {"response_text": f"{lead['company_name']}评分最高，原因是联系方式完整且符合当前区域与行业模拟规则。"}


def build_main_graph(deps: AgentDependencies, *, checkpointer=None):
    builder = StateGraph(AgentState)

    builder.add_node("load_context", lambda state: load_context(state, deps))
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("create_lead_task", lambda state: create_lead_task(state, deps))
    builder.add_node("business_qa", build_business_qa_graph())
    builder.add_node("requirement", build_requirement_graph(deps))
    builder.add_node("business_planning", build_business_planning_graph(deps))
    builder.add_node("research", build_research_graph(deps))
    builder.add_node("score_leads", lambda state: score_leads({**state, "_deps": deps}, deps))
    builder.add_node("mutation", build_mutation_graph(deps))
    builder.add_node("compose_lead_response", lambda state: compose_lead_response(state, deps))
    builder.add_node("answer_lead_query", _lead_query_node)
    builder.add_node("export_results", _response_node("Excel export is not implemented in Phase 1."))
    builder.add_node("general_chat", _response_node("我可以帮助你完成政企营销潜客发现，当前为 Phase 1 Mock Runtime。"))

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "classify_intent")
    builder.add_conditional_edges("classify_intent", route_intent, {
        IntentType.BUSINESS_QA: "business_qa",
        IntentType.LEAD_DISCOVERY: "create_lead_task",
        IntentType.TASK_MODIFICATION: "mutation",
        IntentType.LEAD_QUERY: "answer_lead_query",
        IntentType.EXPORT_REQUEST: "export_results",
        IntentType.GENERAL_CHAT: "general_chat",
    })
    builder.add_edge("business_qa", END)
    builder.add_edge("create_lead_task", "requirement")
    builder.add_edge("requirement", "business_planning")
    builder.add_edge("business_planning", "research")
    builder.add_edge("research", "score_leads")
    builder.add_edge("score_leads", "compose_lead_response")
    builder.add_edge("compose_lead_response", END)
    builder.add_conditional_edges("mutation", route_mutation, {
        MutationScope.DISPLAY_ONLY: "compose_lead_response",
        MutationScope.RANK_ONLY: "score_leads",
        MutationScope.FILTER_ONLY: "score_leads",
        MutationScope.ENRICHMENT_REQUIRED: "research",
        MutationScope.DISCOVERY_REQUIRED: "research",
        MutationScope.FULL_REPLAN: "business_planning",
    })
    builder.add_edge("answer_lead_query", END)
    builder.add_edge("export_results", END)
    builder.add_edge("general_chat", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())
