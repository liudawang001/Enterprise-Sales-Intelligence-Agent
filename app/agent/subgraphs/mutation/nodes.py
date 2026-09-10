from __future__ import annotations

import hashlib

from langgraph.types import interrupt

from app.agent.dependencies import AgentDependencies
from app.agent.enums import MutationScope
from app.agent.state import AgentState
from app.criteria.compiler import CriteriaCompiler
from app.criteria.models import CriteriaDiff, LeadCriteria
from app.domain.task import LeadTask, TaskPatch
from app.mutation.diff import calculate_criteria_diff, criteria_from_task
from app.mutation.invalidation import classify_invalidation
from app.mutation.models import (
    ArtifactReuseContext,
    ReexecutionPlan,
    TaskDiff,
    TaskMutation,
)
from app.mutation.preview import apply_patch_pure, build_preview, calculate_task_diff
from app.tasks.models import TaskReferenceStatus


def _deps(state: AgentState) -> AgentDependencies:
    return state["_deps"]  # type: ignore[return-value]


def resolve_target_task(state: AgentState) -> dict:
    deps = _deps(state)
    resolver = deps.task_reference_resolver
    text = state.get("incoming_text") or ""
    active = deps.task_repository.get_task(state.get("active_task_id"))
    session_id = state.get("session_id") or (active.session_id if active else "")
    reference = resolver.parse(text, active_task_id=state.get("active_task_id"))
    resolution = resolver.resolve(session_id, reference, active_task_id=state.get("active_task_id"))
    update = {
        "task_reference": reference.model_dump(mode="json"),
        "task_reference_status": resolution.status.value,
        "task_candidates": [item.model_dump(mode="json") for item in resolution.candidates],
    }
    if resolution.task_id:
        deps.task_repository.activate_task(session_id, resolution.task_id)
        update.update({"target_task_id": resolution.task_id, "active_task_id": resolution.task_id})
    return update


def route_task_reference(state: AgentState) -> str:
    status = state.get("task_reference_status")
    if status == TaskReferenceStatus.RESOLVED:
        return "RESOLVED"
    if status == TaskReferenceStatus.AMBIGUOUS:
        return "AMBIGUOUS"
    return "NOT_FOUND"


def task_selection_interrupt(state: AgentState) -> dict:
    candidates = state.get("task_candidates", [])
    answer = interrupt({
        "type": "TASK_SELECTION_REQUIRED",
        "candidate_tasks": candidates,
        "question": "你希望修改哪个营销任务？",
    })
    text = answer.get("text", "") if isinstance(answer, dict) else str(answer)
    selected = answer.get("task_id") if isinstance(answer, dict) else None
    if not selected:
        matches = [item for item in candidates if item["task_id"] in text or (item.get("business") and item["business"] in text)]
        if len(matches) == 1:
            selected = matches[0]["task_id"]
    if selected not in {item["task_id"] for item in candidates}:
        raise ValueError("TASK_REFERENCE_AMBIGUOUS")
    _deps(state).task_repository.activate_task(state.get("session_id", ""), selected)
    return {"target_task_id": selected, "active_task_id": selected, "task_reference_status": "RESOLVED"}


def task_not_found(_state: AgentState) -> dict:
    raise ValueError("TASK_NOT_FOUND")


def load_current_task(state: AgentState) -> dict:
    task = _deps(state).task_repository.get_task(state.get("target_task_id") or state.get("active_task_id"))
    if not task:
        raise ValueError("TASK_NOT_FOUND")
    return {
        "current_task_snapshot": task.model_dump(mode="json"),
        "active_task_id": task.task_id,
        "task_version": task.version,
    }


def parse_mutation(state: AgentState) -> dict:
    patch = _deps(state).task_service.parse_mutation(state.get("incoming_text", ""))
    source_message_id = hashlib.sha256(
        f"{state.get('session_id')}:{state.get('active_task_id')}:{state.get('task_version')}:{state.get('incoming_text')}".encode()
    ).hexdigest()
    return {"task_patch": patch.model_dump(mode="json", exclude_none=True), "source_message_id": source_message_id}


def validate_mutation(state: AgentState) -> dict:
    deps = _deps(state)
    patch = TaskPatch.model_validate(state.get("task_patch") or {})
    try:
        deps.mutation_service.validate_patch(patch, task_id=state.get("active_task_id"))
    except ValueError as exc:
        if str(exc) != "RULE_CONFLICT":
            raise
        answer = interrupt({
            "type": "RULE_CONFLICT",
            "task_id": state.get("active_task_id"),
            "question": "当前修改与官方硬性规则冲突，请调整条件后重试。",
            "conflicts": [{"code": "RULE_CONFLICT"}],
        })
        text = answer.get("text", "") if isinstance(answer, dict) else str(answer)
        patch = deps.task_service.parse_mutation(text)
        deps.mutation_service.validate_patch(patch, task_id=state.get("active_task_id"))
        return {"task_patch": patch.model_dump(mode="json", exclude_none=True), "progress": {"event": "TASK_MUTATION_PARSED"}}
    return {"progress": {"event": "TASK_MUTATION_PARSED"}}


def build_mutation_preview(state: AgentState) -> dict:
    task = LeadTask.model_validate(state["current_task_snapshot"])
    preview = build_preview(task, TaskPatch.model_validate(state.get("task_patch") or {}))
    return {"mutation_preview": preview.model_dump(mode="json")}


def calculate_task_diff_node(state: AgentState) -> dict:
    from app.mutation.models import MutationPreview

    value = calculate_task_diff(MutationPreview.model_validate(state["mutation_preview"]))
    return {"task_diff": value.model_dump(mode="json"), "progress": {"event": "TASK_DIFF_READY"}}


def calculate_criteria_diff_node(state: AgentState) -> dict:
    task = LeadTask.model_validate(state["current_task_snapshot"])
    prospective = apply_patch_pure(task, TaskPatch.model_validate(state.get("task_patch") or {}))
    value = calculate_criteria_diff(task, prospective)
    return {"criteria_diff": value.model_dump(mode="json")}


def load_reuse_context(state: AgentState) -> dict:
    value = _deps(state).mutation_service.reuse_analyzer.analyze(state["active_task_id"], state["task_version"])
    return {"artifact_reuse_context": value.model_dump(mode="json")}


def classify_invalidation_node(state: AgentState) -> dict:
    task = LeadTask.model_validate(state["current_task_snapshot"])
    preview = state["mutation_preview"]
    task_diff = TaskDiff.model_validate(state["task_diff"])
    criteria_diff = CriteriaDiff.model_validate(state["criteria_diff"])
    reuse = ArtifactReuseContext.model_validate(state["artifact_reuse_context"])
    newly_required = set(preview["after"].get("required_fields", [])) - set(preview["before"].get("required_fields", []))
    scope, reasons = classify_invalidation(task_diff, criteria_diff, reuse, before_target_count=task.target_count, after_target_count=preview["after"].get("target_count"), newly_required_fields=newly_required)
    return {"mutation_scope": scope.value, "mutation_reason": ",".join(reasons), "progress": {"event": "INVALIDATION_CLASSIFIED", "scope": scope.value}}


def build_reexecution_plan(state: AgentState) -> dict:
    task = LeadTask.model_validate(state["current_task_snapshot"])
    preview = state["mutation_preview"]
    task_diff = TaskDiff.model_validate(state["task_diff"])
    criteria_diff = CriteriaDiff.model_validate(state["criteria_diff"])
    reuse = ArtifactReuseContext.model_validate(state["artifact_reuse_context"])
    required = set(preview["after"].get("required_fields", [])) - set(preview["before"].get("required_fields", []))
    plan = _deps(state).mutation_service.planner.plan(task_diff, criteria_diff, reuse, base_version=task.version, next_version=preview["next_version"], before_target_count=task.target_count, after_target_count=preview["after"].get("target_count"), newly_required_fields=required)
    return {"reexecution_plan_id": plan.plan_id, "reexecution_plan": plan.model_dump(mode="json"), "progress": {"event": "REEXECUTION_PLANNED", "scope": plan.scope.value}}


def apply_mutation(state: AgentState) -> dict:
    deps = _deps(state)
    task = LeadTask.model_validate(state["current_task_snapshot"])
    patch = TaskPatch.model_validate(state.get("task_patch") or {})
    plan = ReexecutionPlan.model_validate(state["reexecution_plan"])
    existing = deps.mutation_repository.find_mutation(task.task_id, state["source_message_id"])
    if existing:
        return {"mutation_id": existing.mutation_id, "task_version": existing.target_version or task.version, "mutation_scope": existing.scope.value}
    mutation = TaskMutation(
        task_id=task.task_id,
        source_message_id=state["source_message_id"],
        base_version=task.version,
        target_version=task.version if plan.scope == MutationScope.NONE else plan.next_version,
        patch=patch,
        preview=state["mutation_preview"],
        task_diff=state["task_diff"],
        criteria_diff=state["criteria_diff"],
        scope=plan.scope,
        reexecution_plan_id=plan.plan_id,
    )
    if plan.scope != MutationScope.NONE:
        updated = deps.task_repository.apply_patch(task.task_id, patch, base_version=task.version, mutation_id=mutation.mutation_id, source_message_id=mutation.source_message_id)
    else:
        updated = task
    deps.mutation_repository.save_mutation(mutation)
    return {"mutation_id": mutation.mutation_id, "task_version": updated.version}


def persist_new_task_version(state: AgentState) -> dict:
    scope = MutationScope(state["mutation_scope"])
    if scope in {MutationScope.NONE, MutationScope.DISPLAY_ONLY, MutationScope.FULL_REPLAN}:
        return {}
    deps = _deps(state)
    task = deps.task_repository.get_task(state["active_task_id"])
    old_id = state.get("criteria_snapshot_id")
    old = deps.rule_service.repository.criteria.get(old_id) if old_id else None
    current = criteria_from_task(task)
    if old:
        changed = set(TaskDiff.model_validate(state["task_diff"]).constraint_fields_changed)
        current.hard_constraints = [item for item in old.hard_constraints if item.field not in changed] + current.hard_constraints
        current.soft_constraints = [item for item in old.soft_constraints if item.field not in changed] + current.soft_constraints
        current.ranking_preferences = [item for item in old.ranking_preferences if item.field not in changed] + current.ranking_preferences
        current.source_rule_ids = old.source_rule_ids
        current.required_fields = task.required_fields or old.required_fields
    current.criteria_hash = CriteriaCompiler.hash(current)
    saved: LeadCriteria = deps.rule_service.repository.save_criteria(current)
    return {"previous_criteria_snapshot_id": old_id, "criteria_snapshot_id": saved.criteria_id}


def persist_reexecution_plan(state: AgentState) -> dict:
    plan = ReexecutionPlan.model_validate(state["reexecution_plan"])
    _deps(state).mutation_repository.save_plan(plan)
    return {"progress": {"event": "REEXECUTION_STARTED", "scope": plan.scope.value}}
