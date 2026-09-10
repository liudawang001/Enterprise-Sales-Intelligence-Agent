import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    _deps: object
    requirement_snapshot: dict
    evidence_chunk_ids: list[str]
    conflict_resolution_text: str | None
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    active_task_id: str | None
    incoming_text: str | None
    intent: str | None
    intent_confidence: float
    task_stage: str | None
    task_status: str | None
    task_version: int
    task_patch: dict | None
    missing_slots: list[str]
    pending_question: dict | None
    clarification_text: str | None
    business_context_refs: list[str]
    criteria_snapshot_id: str | None
    previous_criteria_snapshot_id: str | None
    criteria_diff: dict | None
    official_rule_ids: list[str]
    marketing_rule_ids: list[str]
    user_rule_ids: list[str]
    model_suggestion_ids: list[str]
    normalized_rule_ids: list[str]
    valid_rule_ids: list[str]
    included_rule_ids: list[str]
    suppressed_rule_ids: list[str]
    conflict_ids: list[str]
    planning_status: str | None
    criteria_explain: dict | None
    search_plan_id: str | None
    candidate_set_id: str | None
    candidate_count: int
    verified_set_id: str | None
    verified_count: int
    mutation_scope: str | None
    mutation_reason: str | None
    lead_results: list[dict]
    response_text: str | None
    citations: list[dict]
    rag_warnings: Annotated[list[str], operator.add]
    knowledge_query: dict
    retrieval_hit_summaries: list[dict]
    evidence_count: int
    evidence_status: str
    progress: dict
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict], operator.add]
