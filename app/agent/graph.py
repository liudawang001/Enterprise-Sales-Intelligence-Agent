import logging
import re

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
from app.knowledge.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


def _response_node(text: str):
    def node(_state: AgentState) -> dict:
        return {"response_text": text}
    return node


def _planning_error_node(state: AgentState) -> dict:
    errors = state.get("errors", [])
    detail = errors[-1].get("message", "unknown error") if errors else "unknown error"
    return {"response_text": f"当前筛选条件无法生成可执行 Criteria：{detail}"}


def _lead_query_node(state: AgentState, deps: AgentDependencies) -> dict:
    criteria_id = state.get("criteria_snapshot_id")
    criteria = deps.rule_service.repository.criteria.get(criteria_id) if criteria_id else None
    question = state.get("incoming_text") or ""
    if criteria and re.search(r"条件|要求|Criteria|版本|办公", question, re.IGNORECASE):
        matched = [item for item in criteria.hard_constraints + criteria.soft_constraints if item.field == "office_count" or item.field in question]
        rule_ids = {rid for item in matched for rid in item.source_rule_ids}
        rules = deps.rule_service.repository.get_rules(list(rule_ids))
        sources = "、".join(sorted({rule.source_type.value for rule in rules})) or "当前规则集"
        if matched and all(rule.source_type.value == "MARKETING_RULE" for rule in rules):
            explanation = "多个办公地点不是当前知识库证明的官方办理要求，而是 Demo Marketing Rule，用于潜客优先排序。"
        else:
            explanation = f"该筛选条件来源于{sources}。"
        return {"response_text": f"{explanation}\nCriteria Version: task_version={criteria.task_version}, criteria_id={criteria.criteria_id}, criteria_hash={criteria.criteria_hash}"}
    leads = state.get("lead_results", [])
    if not leads:
        return {"response_text": "当前还没有可解释的潜客评分结果。"}
    lead = leads[0]
    return {"response_text": f"{lead['company_name']}评分最高，原因是联系方式完整且符合当前区域与行业模拟规则。"}


def build_main_graph(deps: AgentDependencies, *, checkpointer=None, knowledge_service: KnowledgeService | None = None):
    if knowledge_service is not None:
        deps.knowledge_service = knowledge_service
    builder = StateGraph(AgentState)

    builder.add_node("load_context", lambda state: load_context(state, deps))
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("create_lead_task", lambda state: create_lead_task(state, deps))
    builder.add_node("business_qa", build_business_qa_graph(knowledge_service))
    builder.add_node("requirement", build_requirement_graph(deps))
    builder.add_node("business_planning", build_business_planning_graph(deps))
    builder.add_node("research", build_research_graph(deps))
    builder.add_node("score_leads", lambda state: score_leads({**state, "_deps": deps}, deps))
    builder.add_node("mutation", build_mutation_graph(deps))
    builder.add_node("compose_lead_response", lambda state: compose_lead_response(state, deps))
    builder.add_node("answer_lead_query", lambda state: _lead_query_node(state, deps))
    builder.add_node("export_results", _response_node("Excel export is not implemented in Phase 1."))
    builder.add_node("general_chat", _response_node("我可以帮助你基于业务证据和结构化筛选条件完成政企营销潜客发现。"))
    builder.add_node("planning_error", _planning_error_node)

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
    builder.add_conditional_edges("business_planning", lambda state: "FAILED" if state.get("planning_status") == "FAILED" else "READY", {"FAILED": "planning_error", "READY": "research"})
    builder.add_edge("research", "score_leads")
    builder.add_edge("score_leads", "compose_lead_response")
    builder.add_edge("compose_lead_response", END)
    builder.add_conditional_edges("mutation", route_mutation, {
        MutationScope.DISPLAY_ONLY: "compose_lead_response",
        MutationScope.RANK_ONLY: "business_planning",
        MutationScope.FILTER_ONLY: "business_planning",
        MutationScope.ENRICHMENT_REQUIRED: "research",
        MutationScope.DISCOVERY_REQUIRED: "research",
        MutationScope.FULL_REPLAN: "business_planning",
    })
    builder.add_edge("answer_lead_query", END)
    builder.add_edge("export_results", END)
    builder.add_edge("general_chat", END)
    builder.add_edge("planning_error", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())
