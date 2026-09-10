from __future__ import annotations

import asyncio

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.evidence.coverage import enterprise_status, evidence_coverage
from app.evidence.models import (
    VerificationBudget,
    VerifiedEnterpriseProfile,
)
from app.evidence.targeted import TargetedVerificationService, VerificationBudgetGuard


def _required_fields(state: AgentState, deps: AgentDependencies) -> list[str]:
    criteria = deps.rule_service.repository.criteria[state["criteria_snapshot_id"]]
    profile = deps.lead_score_repository.active_profile(criteria.business_code)
    scoring_fields = profile.required_fields if profile else []
    return sorted(set(criteria.required_fields) | set(scoring_fields) | {"legal_name"})


def make_load_candidate_set(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        candidate_set_id = state.get("researched_candidate_set_id") or state.get("candidate_set_id")
        if not candidate_set_id or not deps.research_service.repository.get_candidates(candidate_set_id):
            raise ValueError("RESEARCHED_CANDIDATE_SET_NOT_FOUND")
        return {"researched_candidate_set_id": candidate_set_id, "progress": {"event": "VERIFICATION_CANDIDATES_LOADED"}}

    return node


def make_build_resolution_groups(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        candidates = deps.research_service.repository.get_candidates(state["researched_candidate_set_id"])
        groups = deps.entity_resolution_service.blocker.build_groups(candidates)
        return {"progress": {"event": "RESOLUTION_GROUPS_BUILT", "group_count": len(groups)}}

    return node


def make_resolve_entities(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        run = deps.entity_resolution_service.resolve(task_id=state["active_task_id"], candidate_set_id=state["researched_candidate_set_id"])
        enterprises = deps.enterprise_repository.list_for_task(state["active_task_id"])
        return {"resolution_run_id": run.resolution_run_id, "canonical_enterprise_ids": [item.enterprise_id for item in enterprises], "task_stage": "ENTITY_RESOLUTION", "progress": {"event": "ENTITIES_RESOLVED", "enterprise_count": len(enterprises)}}

    return node


def persist_canonical_entities(state: AgentState) -> dict:
    return {"progress": {"event": "CANONICAL_ENTITIES_PERSISTED", "enterprise_count": len(state.get("canonical_enterprise_ids", []))}}


def make_collect_evidence(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        run = deps.evidence_repository.runs.get(state.get("verification_run_id", ""))
        if not run:
            budget = (
                deps.targeted_verification_service.guard.budget
                if deps.targeted_verification_service
                else VerificationBudget()
            )
            run = deps.verification_service.start_run(task_id=state["active_task_id"], candidate_set_id=state["researched_candidate_set_id"], resolution_run_id=state["resolution_run_id"], budget=budget)
        values = deps.verification_service.collect_evidence(run)
        return {"verification_run_id": run.verification_run_id, "verification_max_rounds": run.budget.max_rounds, "progress": {"event": "EVIDENCE_COLLECTED", "evidence_count": len(values)}}

    return node


def normalize_evidence(state: AgentState) -> dict:
    return {"progress": {"event": "EVIDENCE_NORMALIZED"}}


def make_detect_field_conflicts(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        conflicts = 0
        for enterprise_id in state.get("canonical_enterprise_ids", []):
            grouped = {}
            for item in deps.evidence_repository.list_evidence(enterprise_id):
                grouped.setdefault(item.field_name, set()).add(repr(item.normalized_value))
            conflicts += sum(len(values) > 1 for values in grouped.values())
        return {"progress": {"event": "FIELD_CONFLICTS_DETECTED", "conflict_count": conflicts}}

    return node


def make_resolve_fields(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        required = _required_fields(state, deps)
        unresolved = []
        conflicting = []
        for enterprise_id in state.get("canonical_enterprise_ids", []):
            fields = deps.verification_service.resolve_fields(enterprise_id, required)
            if any(fields[name].status in {"MISSING", "UNVERIFIED"} for name in required):
                unresolved.append(enterprise_id)
            if any(item.status == "CONFLICTING" for item in fields.values()):
                conflicting.append(enterprise_id)
        return {"unresolved_enterprise_ids": unresolved, "conflicting_enterprise_ids": conflicting, "progress": {"event": "FIELDS_RESOLVED"}}

    return node


def make_targeted_verification(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        service = deps.targeted_verification_service
        if not service:
            return {
                "verification_round": state.get("verification_round", 0) + 1,
                "unresolved_enterprise_ids": [],
                "warnings": ["TARGETED_VERIFICATION_PROVIDER_NOT_CONFIGURED"],
            }
        local_service = TargetedVerificationService(
            deps.evidence_repository,
            service.provider,
            VerificationBudgetGuard(service.guard.budget),
        )
        if not local_service.guard.start_round():
            return {
                "verification_round": state.get("verification_round", 0) + 1,
                "unresolved_enterprise_ids": [],
                "warnings": ["VERIFICATION_BUDGET_EXHAUSTED"],
            }
        required = _required_fields(state, deps)
        enriched = 0
        for enterprise_id in state.get("unresolved_enterprise_ids", [
        ])[: local_service.guard.budget.max_candidates]:
            fields = {
                name: value
                for (stored_id, name), value in deps.evidence_repository.resolved_fields.items()
                if stored_id == enterprise_id
            }
            profile = VerifiedEnterpriseProfile(
                verification_run_id=state["verification_run_id"],
                enterprise_id=enterprise_id,
                fields=fields,
                status=enterprise_status(fields),
                evidence_coverage=evidence_coverage(fields, required),
                required_fields=required,
            )
            missing = deps.verification_service.fields_needing_enrichment(profile)
            enriched += len(asyncio.run(local_service.enrich(profile, missing)))
        run = deps.evidence_repository.runs[state["verification_run_id"]]
        deps.evidence_repository.save_run(
            run.model_copy(
                update={
                    "used_budget": {
                        "extra_tool_calls": local_service.guard.used_calls,
                        "web_pages": local_service.guard.used_pages,
                        "rounds": local_service.guard.rounds,
                    }
                }
            )
        )
        return {
            "verification_round": state.get("verification_round", 0) + 1,
            "unresolved_enterprise_ids": [],
            "progress": {
                "event": "TARGETED_VERIFICATION_COMPLETED",
                "evidence_count": enriched,
            },
        }

    return node


def make_build_verified_profiles(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        run = deps.evidence_repository.runs[state["verification_run_id"]]
        required = _required_fields(state, deps)
        profiles = [deps.verification_service.build_profile(run, enterprise_id, required) for enterprise_id in state.get("canonical_enterprise_ids", [])]
        deps.verification_service.finish_run(run, profiles, state.get("warnings", []))
        return {"verified_profile_ids": [item.profile_id for item in profiles], "verified_count": len(profiles), "task_stage": "VERIFICATION", "progress": {"event": "VERIFIED_PROFILES_BUILT", "verified_count": len(profiles)}}

    return node
