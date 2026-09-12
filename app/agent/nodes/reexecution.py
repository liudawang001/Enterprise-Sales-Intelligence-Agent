from __future__ import annotations

import asyncio
from langchain_core.runnables import RunnableLambda

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.criteria.evaluator import DefaultCriteriaEvaluator
from app.execution.models import TaskExecutionSnapshot
from app.mutation.models import ReexecutionPlan, ReexecutionPlanStatus
from app.research.models import CandidateSet, CandidateStatus
from app.observability.context import get_request_context
from app.observability.metrics import metrics


def _lead_rows(deps: AgentDependencies, task_id: str, lead_set_id: str | None) -> list[dict]:
    lead_set = deps.lead_score_repository.lead_sets.get(lead_set_id or "")
    if not lead_set:
        return []
    scores = [item for item in deps.lead_score_repository.list_for_task(task_id) if item.enterprise_id in lead_set.lead_ids]
    latest = {}
    for score in scores:
        latest[score.enterprise_id] = score
    rows = []
    for enterprise_id in lead_set.lead_ids:
        score = latest.get(enterprise_id)
        if not score:
            continue
        enterprise = deps.enterprise_repository.get_enterprise(enterprise_id)
        reason = deps.lead_score_repository.reasons.get(enterprise_id)
        rows.append({
            "enterprise_id": enterprise_id,
            "company_name": enterprise.canonical_name if enterprise else enterprise_id,
            "score": score.total_score,
            "rank_status": score.rank_status.value,
            "verification_status": score.verification_status,
            "evidence_coverage": score.evidence_coverage,
            "score_breakdown": [item.model_dump(mode="json") for item in score.component_scores],
            "recommendation_reason": reason.summary if reason else "",
            "evidence_ids": reason.evidence_ids if reason else [],
        })
    return rows


def make_select_existing_leads(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        task = deps.task_repository.get_task(state["active_task_id"])
        context = state.get("artifact_reuse_context") or {}
        lead_set_id = context.get("lead_score_set_id") or state.get("lead_set_id")
        rows = _lead_rows(deps, task.task_id, lead_set_id)[: task.target_count]
        return {"lead_results": rows, "lead_set_id": lead_set_id, "verified_set_id": lead_set_id, "progress": {"event": "ARTIFACT_REUSED", "artifact_id": lead_set_id}}

    return node


def make_reuse_verified_profiles(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        run = deps.evidence_repository.latest_run_for_task(state["active_task_id"])
        profile_ids = list(run.profile_ids) if run else []
        return {"verified_profile_ids": profile_ids, "verified_count": len(profile_ids), "progress": {"event": "ARTIFACT_REUSED", "artifact": "verified_profiles", "count": len(profile_ids)}}

    return node


def make_filter_existing(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        context = state["artifact_reuse_context"]
        parent_id = context.get("researched_candidate_set_id") or context.get("raw_candidate_set_id")
        parent = deps.research_service.repository.candidate_sets.get(parent_id or "")
        criteria = deps.rule_service.repository.criteria[state["criteria_snapshot_id"]]
        if not parent:
            raise ValueError("REUSABLE_ARTIFACT_MISSING")
        evaluator = DefaultCriteriaEvaluator()
        selected = []
        for candidate in deps.research_service.repository.get_candidates(parent_id):
            if evaluator.evaluate_hard_constraints(candidate.model_dump(), criteria) != "NO_MATCH":
                selected.append(candidate.candidate_id)
            else:
                deps.research_service.repository.save_candidate(candidate.model_copy(update={"status": CandidateStatus.FILTERED_OUT}))
        filtered = deps.research_service.repository.save_candidate_set(CandidateSet(research_run_id=parent.research_run_id, parent_set_id=parent_id, stage="FILTERED_REEXECUTION", criteria_snapshot_id=criteria.criteria_id, search_plan_id=parent.search_plan_id, candidate_ids=selected))
        reused_profiles = []
        new_candidates = []
        for candidate_id in selected:
            link = deps.enterprise_repository.candidate_links.get(candidate_id)
            profile = deps.evidence_repository.get_profile(link.enterprise_id) if link else None
            if profile:
                reused_profiles.append(profile.profile_id)
            else:
                new_candidates.append(candidate_id)
        update = {
            "filtered_candidate_set_id": filtered.candidate_set_id,
            "candidate_count": filtered.candidate_count,
            "reused_verified_profile_ids": list(dict.fromkeys(reused_profiles)),
            "verification_needed": bool(new_candidates),
            "progress": {"event": "FILTER_REEXECUTION_COMPLETED", "reused_count": len(reused_profiles), "new_count": len(new_candidates)},
        }
        task = deps.task_repository.get_task(state["active_task_id"])
        if filtered.candidate_count < (task.target_count or 0):
            plan = ReexecutionPlan.model_validate(state["reexecution_plan"])
            plan = plan.model_copy(update={"final_scope": "DISCOVERY_REQUIRED", "escalation_reason": "REUSABLE_POOL_INSUFFICIENT_AT_RUNTIME"})
            deps.mutation_repository.save_plan(plan)
            update.update({"mutation_scope": "DISCOVERY_REQUIRED", "reexecution_plan": plan.model_dump(mode="json"), "verification_needed": False})
        if new_candidates:
            verification_set = deps.research_service.repository.save_candidate_set(CandidateSet(research_run_id=parent.research_run_id, parent_set_id=filtered.candidate_set_id, stage="VERIFY_NEW", criteria_snapshot_id=criteria.criteria_id, search_plan_id=parent.search_plan_id, candidate_ids=new_candidates))
            update.update({"candidate_set_id": verification_set.candidate_set_id, "researched_candidate_set_id": verification_set.candidate_set_id})
        else:
            update["verified_profile_ids"] = list(dict.fromkeys(reused_profiles))
        return update

    return node


def route_verification_needed(state: AgentState) -> str:
    if state.get("mutation_scope") == "DISCOVERY_REQUIRED":
        return "DISCOVERY"
    return "VERIFY" if state.get("verification_needed") else "SCORE"


def make_targeted_enrichment(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        context = state["artifact_reuse_context"]
        set_id = context.get("researched_candidate_set_id") or context.get("filtered_candidate_set_id")
        candidate_set = deps.research_service.repository.candidate_sets.get(set_id or "")
        if not candidate_set:
            raise ValueError("REUSABLE_ARTIFACT_MISSING")
        fields = state.get("reexecution_plan", {}).get("required_fields", [])
        for candidate in deps.research_service.repository.get_candidates(set_id):
            asyncio.run(deps.research_service.targeted_enrich_fields(candidate_set.research_run_id, candidate.candidate_id, fields))
        return {"candidate_set_id": set_id, "researched_candidate_set_id": set_id, "verification_needed": True, "reused_verified_profile_ids": [], "progress": {"event": "TARGETED_ENRICHMENT_COMPLETED", "fields": fields}}

    return node


def merge_verified_profiles(state: AgentState) -> dict:
    reused = state.get("reused_verified_profile_ids", []) if state.get("mutation_scope") in {"FILTER_ONLY", "ENRICHMENT_REQUIRED"} else []
    values = list(dict.fromkeys(reused + state.get("verified_profile_ids", [])))
    return {"verified_profile_ids": values, "verified_count": len(values)}


def make_promote_execution_snapshot(deps: AgentDependencies):
    def promote(state: AgentState, fence_allowed: bool = True) -> dict:
        task = deps.task_repository.get_task(state["active_task_id"])
        version = state.get("task_version", task.version)
        reuse = state.get("artifact_reuse_context") or {}
        plan_id = state.get("reexecution_plan_id")
        if state.get("mutation_scope") == "NONE":
            current = deps.execution_snapshot_repository.current(task.task_id)
            if plan_id:
                plan = deps.mutation_repository.get_plan(plan_id)
                if plan:
                    deps.mutation_repository.save_plan(plan.model_copy(update={"status": ReexecutionPlanStatus.COMPLETED}))
            return {"execution_snapshot_id": current.snapshot_id if current else None, "progress": {"event": "ARTIFACT_REUSED"}}
        scope = state.get("mutation_scope")
        partial = scope in {"DISPLAY_ONLY", "RANK_ONLY", "FILTER_ONLY", "ENRICHMENT_REQUIRED"}
        criteria_snapshot_id = reuse.get("criteria_snapshot_id") if scope == "DISPLAY_ONLY" else state.get("criteria_snapshot_id")
        search_plan_id = reuse.get("search_plan_id") if partial else state.get("search_plan_id")
        raw_candidate_set_id = reuse.get("raw_candidate_set_id") if partial else state.get("raw_candidate_set_id")
        filtered_candidate_set_id = state.get("filtered_candidate_set_id") if scope == "FILTER_ONLY" else reuse.get("filtered_candidate_set_id") if partial else state.get("filtered_candidate_set_id")
        researched_candidate_set_id = reuse.get("researched_candidate_set_id") if partial else state.get("researched_candidate_set_id") or state.get("candidate_set_id")
        snapshot = TaskExecutionSnapshot(
            task_id=task.task_id,
            task_version=version,
            criteria_snapshot_id=criteria_snapshot_id,
            search_plan_id=search_plan_id,
            raw_candidate_set_id=raw_candidate_set_id,
            filtered_candidate_set_id=filtered_candidate_set_id,
            researched_candidate_set_id=researched_candidate_set_id,
            verified_lead_set_id=state.get("verified_set_id") or reuse.get("verified_lead_set_id"),
            scoring_profile_id=state.get("scoring_profile_id") or reuse.get("scoring_profile_id"),
            lead_score_set_id=state.get("lead_set_id") or reuse.get("lead_score_set_id"),
        )
        if not fence_allowed:
            deps.execution_snapshot_repository.save(snapshot.model_copy(update={"is_current": False, "validity": "SUPERSEDED"}))
            metrics.add("stale_promotion_rejected_total")
            return {"execution_snapshot_id": snapshot.snapshot_id, "progress": {"event": "ARTIFACT_PROMOTION_REJECTED"}, "warnings": ["STALE_RUN_FENCE"]}
        promoted = deps.execution_snapshot_repository.promote(snapshot, current_task_version=task.version)
        event = "TASK_VERSION_ACTIVATED" if promoted else "ARTIFACT_PROMOTION_REJECTED"
        if plan_id:
            plan = deps.mutation_repository.get_plan(plan_id)
            if plan:
                deps.mutation_repository.save_plan(plan.model_copy(update={"status": ReexecutionPlanStatus.COMPLETED if promoted else ReexecutionPlanStatus.SUPERSEDED}))
        return {"execution_snapshot_id": snapshot.snapshot_id, "progress": {"event": event}, "warnings": [] if promoted else ["STALE_EXECUTION"]}

    def sync_node(state: AgentState) -> dict:
        context = get_request_context()
        allowed = True
        if context and context.run_id and context.fence_token is not None:
            validator = getattr(deps.execution_coordinator, "can_promote_cached", None)
            allowed = validator(context.run_id, context.fence_token) if validator else True
        return promote(state, allowed)

    async def async_node(state: AgentState) -> dict:
        context = get_request_context()
        allowed = True
        if context and context.run_id and context.fence_token is not None:
            allowed = await deps.execution_coordinator.can_promote(context.run_id, context.fence_token)
        return promote(state, allowed)

    return RunnableLambda(sync_node, afunc=async_node, name="promote_execution_snapshot")
