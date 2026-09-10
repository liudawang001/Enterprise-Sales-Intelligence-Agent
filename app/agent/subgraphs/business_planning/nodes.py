from __future__ import annotations

import os
import re
import logging
from typing import Any

from langgraph.types import interrupt

from app.agent.dependencies import AgentDependencies
from app.agent.enums import TaskStage
from app.agent.state import AgentState
from app.domain.task import ConstraintPatch, TaskPatch
from app.rules.models import BusinessRule, ConstraintType, OfficialRuleExtractionInput, RuleEvidenceChunk, RuleOperator, RuleSourceType

logger = logging.getLogger(__name__)


def _deps(state: AgentState) -> AgentDependencies:
    return state["_deps"]  # type: ignore[return-value]


def load_task_requirements(state: AgentState) -> dict[str, Any]:
    task = _deps(state).task_repository.get_task(state.get("active_task_id"))
    if not task:
        return {"planning_status": "FAILED", "errors": [{"node": "load_task_requirements", "message": "Task not found"}]}
    snapshot = {"task_id": task.task_id, "task_version": task.version, "business_code": task.business, "region": task.region, "target_count": task.target_count, "constraints": task.constraints}
    update: dict[str, Any] = {"requirement_snapshot": snapshot, "task_version": task.version}
    if state.get("criteria_snapshot_id"):
        update["previous_criteria_snapshot_id"] = state["criteria_snapshot_id"]
    return update


def retrieve_business_evidence(state: AgentState) -> dict[str, Any]:
    deps = _deps(state)
    snapshot = state.get("requirement_snapshot", {})
    service = getattr(deps, "knowledge_service", None)
    evidence: list[dict[str, Any]] = []
    if service and hasattr(service, "analyze_query") and hasattr(service, "retrieve"):
        try:
            queries = ["适用对象", "办理条件", "业务限制", "业务特点", "推荐客户"]
            seen: set[str] = set()
            for suffix in queries:
                query = service.analyze_query(f"{snapshot.get('business_code', '')}{suffix}")
                hits, _ = service.retrieve(query, top_k=4)
                for hit in hits:
                    item = {"chunk_id": str(hit.chunk_id), "document_id": str(hit.document_id), "content": hit.content, "page_start": hit.page_start, "page_end": hit.page_end, "authority": hit.metadata.get("authority")}
                    if item["chunk_id"] not in seen:
                        evidence.append(item); seen.add(item["chunk_id"])
                    if len(evidence) >= 20:
                        break
                if len(evidence) >= 20:
                    break
        except Exception as exc:
            return {"business_context_refs": [], "evidence_chunk_ids": [], "warnings": [f"RAG_RETRIEVAL_FAILED: {exc}"], "planning_status": "PARTIAL"}
    refs = deps.rule_service.repository.save_evidence(evidence)
    return {"business_context_refs": refs, "evidence_chunk_ids": refs, "planning_status": "EVIDENCE_RETRIEVED"}


def extract_official_rules(state: AgentState) -> dict[str, Any]:
    deps = _deps(state)
    snapshot = state.get("requirement_snapshot", {})
    evidence = deps.rule_service.repository.get_evidence(state.get("evidence_chunk_ids", []))
    official_evidence = [item for item in evidence if item.get("authority") != "MARKETING_EXPERIENCE"]
    payload = OfficialRuleExtractionInput(business=snapshot.get("business_code", ""), task_requirements=snapshot, evidence_chunks=[RuleEvidenceChunk.model_validate(item) for item in official_evidence])
    try:
        result = deps.rule_service.official_extractor.extract(payload)
        rules, warnings = deps.rule_service.official_rules_from_evidence(snapshot.get("business_code", ""), result.rules, official_evidence)
        return {"official_rule_ids": [r.rule_id for r in rules], "warnings": warnings + result.warnings + result.ignored_facts}
    except Exception as exc:
        return {"official_rule_ids": [], "warnings": [f"RULE_EXTRACTION_FAILED: {exc}"], "planning_status": "PARTIAL"}


def load_marketing_rules(state: AgentState) -> dict[str, Any]:
    snapshot = state.get("requirement_snapshot", {})
    rules = _deps(state).rule_service.repository.list_marketing(snapshot.get("business_code", ""), snapshot.get("region"))
    return {"marketing_rule_ids": [r.rule_id for r in rules]}


def build_user_rules(state: AgentState) -> dict[str, Any]:
    snapshot = state.get("requirement_snapshot", {})
    rules: list[BusinessRule] = []
    business = snapshot.get("business_code") or ""
    region = snapshot.get("region")
    if region:
        rules.append(BusinessRule(business_code=business, field="region", operator=RuleOperator.EQ, value=region, value_type="STRING", source_type=RuleSourceType.USER_REQUIREMENT, constraint_type=ConstraintType.HARD, rationale="用户指定地区", source_message_id=state.get("incoming_text"), source_key=f"user:{snapshot.get('task_id')}:{snapshot.get('task_version')}:region:EQ:{region}"))
    for constraint in snapshot.get("constraints", []) or []:
        if constraint.get("operation") in {"REMOVE", "CLEAR"}:
            continue
        field, operator, value = constraint.get("field"), constraint.get("operator") or "EQ", constraint.get("value")
        if not field or value is None:
            continue
        ctype = ConstraintType(constraint.get("constraint_type") or "HARD")
        source_message = state.get("incoming_text") or ""
        source_key = f"user:{snapshot.get('task_id')}:{snapshot.get('task_version')}:{field}:{operator}:{value}"
        rules.append(BusinessRule(business_code=business, field=field, operator=operator, value=value, value_type="AUTO", source_type=RuleSourceType.USER_REQUIREMENT, constraint_type=ctype, rationale="用户当前对话要求", source_message_id=source_message, source_key=source_key))
    saved_rules = [_deps(state).rule_service.repository.upsert(rule) for rule in rules]
    return {"user_rule_ids": [r.rule_id for r in saved_rules]}


def generate_model_suggestions(state: AgentState) -> dict[str, Any]:
    if os.getenv("MODEL_SUGGESTIONS_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return {"model_suggestion_ids": []}
    deps = _deps(state)
    snapshot = state.get("requirement_snapshot", {})
    evidence = deps.rule_service.repository.get_evidence(state.get("evidence_chunk_ids", []))
    try:
        suggestions = deps.rule_service.suggestion_generator.generate({"business": snapshot.get("business_code"), "requirements": snapshot, "evidence": evidence})
    except Exception as exc:
        return {"model_suggestion_ids": [], "warnings": [f"MODEL_SUGGESTION_DEGRADED: {exc}"]}
    rules = []
    for suggestion in suggestions[:5]:
        if not suggestion.evidence_refs or not all(ref in deps.rule_service.repository.evidence for ref in suggestion.evidence_refs):
            continue
        source_key = f"model:{snapshot.get('task_id')}:{snapshot.get('task_version')}:{suggestion.field}:{suggestion.operator}:{suggestion.value}"
        rule = BusinessRule(business_code=snapshot.get("business_code", ""), field=suggestion.field, operator=suggestion.operator, value=suggestion.value, value_type="AUTO", source_type=RuleSourceType.MODEL_SUGGESTION, constraint_type=ConstraintType.SOFT, weight=0.3, confidence=suggestion.confidence, rationale=suggestion.rationale, evidence_refs=suggestion.evidence_refs, source_key=source_key)
        saved = deps.rule_service.repository.upsert(rule)
        rules.append(saved)
    return {"model_suggestion_ids": [r.rule_id for r in rules]}


def normalize_rules(state: AgentState) -> dict[str, Any]:
    repository = _deps(state).rule_service.repository
    ids = state.get("official_rule_ids", []) + state.get("marketing_rule_ids", []) + state.get("user_rule_ids", []) + state.get("model_suggestion_ids", [])
    all_rules = repository.get_rules(ids)
    normalized, warnings = [], list(state.get("warnings", []))
    for rule in all_rules:
        try:
            item = _deps(state).rule_service.normalizer.normalize(rule)
            repository.rules[item.rule_id] = item
            normalized.append(item)
        except Exception as exc:
            warnings.append(str(exc))
    return {"normalized_rule_ids": [r.rule_id for r in normalized], "warnings": warnings}


def validate_rules(state: AgentState) -> dict[str, Any]:
    valid, invalid = [], []
    repository = _deps(state).rule_service.repository
    for rule in repository.get_rules(state.get("normalized_rule_ids", [])):
        try:
            _deps(state).rule_service.validator.validate(rule)
            valid.append(rule)
        except Exception as exc:
            invalid.append({"rule_id": rule.rule_id, "message": str(exc)})
    return {"valid_rule_ids": [r.rule_id for r in valid], "errors": invalid}


def detect_conflicts(state: AgentState) -> dict[str, Any]:
    repository = _deps(state).rule_service.repository
    conflicts = _deps(state).rule_service.conflicts.detect(repository.get_rules(state.get("valid_rule_ids", [])))
    ids = repository.save_conflicts(conflicts)
    return {"conflict_ids": ids, "planning_status": "CONFLICT" if any(c.blocking for c in conflicts) else "VALIDATED"}


def build_conflict_question(state: AgentState) -> dict[str, Any]:
    conflicts = [c.model_dump(mode="json") for c in _deps(state).rule_service.repository.get_conflicts(state.get("conflict_ids", [])) if c.blocking]
    return {"pending_question": {"text": "当前用户筛选条件与业务规则冲突，请调整条件后重试。", "conflicts": conflicts}}


def conflict_interrupt(state: AgentState) -> dict[str, Any]:
    conflicts = _deps(state).rule_service.repository.get_conflicts(state.get("conflict_ids", []))
    answer = interrupt({"type": "RULE_CONFLICT", "task_id": state.get("active_task_id"), "conflicts": [c.model_dump(mode="json") for c in conflicts if c.blocking], "question": state.get("pending_question")})
    return {"conflict_resolution_text": answer.get("text", "") if isinstance(answer, dict) else str(answer)}


def apply_conflict_resolution(state: AgentState) -> dict[str, Any]:
    text = state.get("conflict_resolution_text", "")
    task_id = state.get("active_task_id")
    if task_id and text:
        constraints = [ConstraintPatch(field="member_count", operation="REMOVE")]
        match = re.search(r"(?:至少|不少于)\s*(\d+)", text)
        if match:
            constraints.append(ConstraintPatch(field="member_count", operation="ADD", operator="GTE", value=int(match.group(1)), constraint_type="HARD"))
        _deps(state).task_service.apply_patch(task_id, TaskPatch(constraints=constraints))
    return {"planning_status": "RESOLVED"}


def resolve_rule_set(state: AgentState) -> dict[str, Any]:
    repository = _deps(state).rule_service.repository
    included, suppressed = _deps(state).rule_service.conflicts.resolve(repository.get_rules(state.get("valid_rule_ids", [])), repository.get_conflicts(state.get("conflict_ids", [])))
    for rule in included + suppressed:
        repository.rules[rule.rule_id] = rule
    return {"included_rule_ids": [r.rule_id for r in included], "suppressed_rule_ids": [r.rule_id for r in suppressed]}


def compile_criteria(state: AgentState) -> dict[str, Any]:
    snapshot = state.get("requirement_snapshot", {})
    repository = _deps(state).rule_service.repository
    criteria = _deps(state).rule_service.compile(task_id=snapshot.get("task_id", state.get("active_task_id", "")), task_version=snapshot.get("task_version", 1), business_code=snapshot.get("business_code", ""), region=snapshot.get("region", ""), target_count=snapshot.get("target_count") or 1, rules=repository.get_rules(state.get("included_rule_ids", [])), warnings=list(state.get("warnings", [])))
    update: dict[str, Any] = {"criteria_snapshot_id": criteria.criteria_id, "planning_status": "COMPILED"}
    previous_id = state.get("previous_criteria_snapshot_id")
    previous = repository.criteria.get(previous_id) if previous_id else None
    if previous and previous.criteria_id != criteria.criteria_id:
        from app.criteria.diff import diff_criteria
        update["criteria_diff"] = diff_criteria(previous, criteria).model_dump(mode="json")
    return update


def validate_criteria_node(state: AgentState) -> dict[str, Any]:
    from app.criteria.validator import validate_criteria
    try:
        criteria = _deps(state).rule_service.repository.criteria[state["criteria_snapshot_id"]]
        validate_criteria(criteria)
        return {"planning_status": "VALIDATED"}
    except Exception as exc:
        return {"planning_status": "FAILED", "errors": [{"node": "validate_criteria", "message": str(exc)}]}


def persist_criteria_snapshot(state: AgentState) -> dict[str, Any]:
    task = _deps(state).task_repository.get_task(state.get("active_task_id"))
    if task:
        _deps(state).task_repository.set_status(task.task_id, stage=TaskStage.BUSINESS_PLANNING)
        logger.info("phase3_planning task_id=%s task_version=%s business_code=%s official_rule_count=%s marketing_rule_count=%s user_rule_count=%s model_suggestion_count=%s conflict_count=%s included_rule_count=%s suppressed_rule_count=%s criteria_id=%s", task.task_id, task.version, state.get("requirement_snapshot", {}).get("business_code"), len(state.get("official_rule_ids", [])), len(state.get("marketing_rule_ids", [])), len(state.get("user_rule_ids", [])), len(state.get("model_suggestion_ids", [])), len(state.get("conflict_ids", [])), len(state.get("included_rule_ids", [])), len(state.get("suppressed_rule_ids", [])), state.get("criteria_snapshot_id"))
    return {"criteria_snapshot_id": state.get("criteria_snapshot_id")}


load_mock_business_context = retrieve_business_evidence
build_mock_criteria = compile_criteria
