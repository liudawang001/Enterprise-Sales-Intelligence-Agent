import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
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
    search_plan_id: str | None
    candidate_set_id: str | None
    candidate_count: int
    verified_set_id: str | None
    verified_count: int
    mutation_scope: str | None
    mutation_reason: str | None
    lead_results: list[dict]
    response_text: str | None
    progress: dict
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict], operator.add]
