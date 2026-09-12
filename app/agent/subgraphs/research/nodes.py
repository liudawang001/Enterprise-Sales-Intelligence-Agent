from __future__ import annotations

import asyncio
from uuid import uuid4

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.criteria.evaluator import DefaultCriteriaEvaluator


def _criteria(state: AgentState, deps: AgentDependencies):
    criteria_id = state.get("criteria_snapshot_id")
    return (
        deps.rule_service.repository.criteria.get(criteria_id) if criteria_id else None
    )


def _execution_is_current(deps: AgentDependencies, run_id: str) -> bool:
    run = deps.research_service.repository.runs.get(run_id)
    if not run:
        return False
    criteria = deps.rule_service.repository.criteria.get(run.criteria_snapshot_id)
    task = deps.task_repository.get_task(run.task_id)
    return bool(criteria and task and criteria.task_version == task.version)


def _superseded_batch(deps: AgentDependencies, run_id: str, stage: str) -> str:
    ref = deps.research_service.repository.save_batch_result(str(uuid4()), [], research_run_id=run_id, stage=stage)
    deps.research_service.repository.record_event(run_id, "STALE_EXECUTION", stage=stage)
    return ref


def make_load_criteria(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        criteria = _criteria(state, deps)
        if not criteria:
            task = deps.task_repository.get_task(state.get("active_task_id"))
            if (
                not task
                or not task.business
                or not task.region
                or not task.target_count
            ):
                raise ValueError("CRITERIA_NOT_FOUND")
            criteria = deps.rule_service.compile(
                task_id=task.task_id,
                task_version=task.version,
                business_code=task.business,
                region=task.region,
                target_count=task.target_count,
                rules=[],
            )
        return {
            "criteria_snapshot_id": criteria.criteria_id,
            "progress": {"event": "RESEARCH_CRITERIA_LOADED"},
        }

    return node


def make_build_search_plan(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        run, plan = deps.research_service.build_plan(_criteria(state, deps))
        queries = [item.model_dump(mode="json") for item in plan.discovery_queries]
        batches = [[query] for query in queries]
        return {
            "research_run_id": run.research_run_id,
            "search_plan_id": plan.plan_id,
            "discovery_batches": batches,
            "expansion_round": 0,
            "progress": {
                "event": "RESEARCH_PLAN_CREATED",
                "candidate_target": plan.candidate_target,
            },
        }

    return node


def validate_search_plan(state: AgentState) -> dict:
    if not state.get("search_plan_id") or not state.get("discovery_batches"):
        raise ValueError("INVALID_SEARCH_PLAN")
    return {"progress": {"event": "RESEARCH_PLAN_VALIDATED"}}


def persist_search_plan(state: AgentState) -> dict:
    return {
        "progress": {
            "event": "RESEARCH_PLAN_PERSISTED",
            "search_plan_id": state["search_plan_id"],
        }
    }


def dispatch_discovery(state: AgentState) -> dict:
    return {
        "progress": {
            "event": "DISCOVERY_STARTED",
            "total_batches": len(state.get("discovery_batches", [])),
        }
    }


def make_run_discovery_batch(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        if not _execution_is_current(deps, state["research_run_id"]):
            return {"discovery_result_refs": [_superseded_batch(deps, state["research_run_id"], "DISCOVERY")]}
        ref = asyncio.run(
            deps.research_service.run_discovery_batch(
                state["research_run_id"], state.get("discovery_batch", [])
            )
        )
        return {"discovery_result_refs": [ref]}

    return node


def make_merge_discovery(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        result = deps.research_service.merge_discovery(
            state["research_run_id"], state.get("discovery_result_refs", [])
        )
        ids = list(result.candidate_ids)
        plan = deps.research_service.repository.plans[state["search_plan_id"]]
        batches = [
            ids[i : i + plan.batch_size] for i in range(0, len(ids), plan.batch_size)
        ] or [[]]
        return {
            "raw_candidate_set_id": result.candidate_set_id,
            "candidate_count": result.candidate_count,
            "enrichment_batches": batches,
            "progress": {
                "event": "DISCOVERY_COMPLETED",
                "candidate_count": result.candidate_count,
            },
        }

    return node


def make_route_more_candidates(deps: AgentDependencies):
    def route(state: AgentState) -> str:
        plan = deps.research_service.repository.plans[state["search_plan_id"]]
        return (
            "EXPAND"
            if state.get("candidate_count", 0) < plan.candidate_target
            and state.get("expansion_round", 0) < plan.max_expansion_rounds
            else "CONTINUE"
        )

    return route


def normalize_candidates(state: AgentState) -> dict:
    return {
        "progress": {
            "event": "CANDIDATES_NORMALIZED",
            "candidate_count": state.get("candidate_count", 0),
        }
    }


def persist_raw_candidate_set(state: AgentState) -> dict:
    return {
        "progress": {
            "event": "RAW_CANDIDATE_SET_PERSISTED",
            "candidate_set_id": state.get("raw_candidate_set_id"),
        }
    }


def make_expand_search_plan(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        plan = deps.research_service.repository.plans[state["search_plan_id"]]
        round_number = state.get("expansion_round", 0) + 1
        # Expansion broadens only query phrasing/providers; hard filters and region remain unchanged.
        queries = [
            item.model_copy(
                update={
                    "query_id": str(__import__("uuid").uuid4()),
                    "page": round_number + 1,
                    "query_text": f"{item.query_text or ''} 企业名录".strip(),
                }
            ).model_dump(mode="json")
            for item in plan.discovery_queries
        ]
        return {
            "expansion_round": round_number,
            "discovery_batches": [[query] for query in queries],
            "progress": {"event": "SEARCH_EXPANDED", "round": round_number},
        }

    return node


def dispatch_cheap_enrichment(state: AgentState) -> dict:
    return {
        "progress": {
            "event": "ENRICHMENT_STARTED",
            "total_batches": len(state.get("enrichment_batches", [])),
        }
    }


def make_run_enrichment_batch(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        if not _execution_is_current(deps, state["research_run_id"]):
            return {"enrichment_result_refs": [_superseded_batch(deps, state["research_run_id"], "ENRICHMENT")]}
        ref = asyncio.run(
            deps.research_service.enrich_batch(
                state["research_run_id"], state.get("enrichment_batch", [])
            )
        )
        return {"enrichment_result_refs": [ref]}

    return node


def make_apply_hard_filters(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        result = deps.research_service.apply_hard_filters(
            state["research_run_id"],
            state["cheap_enriched_set_id"],
            _criteria(state, deps),
        )
        return {
            "filtered_candidate_set_id": result.candidate_set_id,
            "candidate_count": result.candidate_count,
            "progress": {
                "event": "FILTER_COMPLETED",
                "candidate_count": result.candidate_count,
            },
        }

    return node


def make_persist_cheap_enriched_set(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        result = deps.research_service.persist_cheap_enriched_set(
            state["research_run_id"], state["raw_candidate_set_id"]
        )
        return {
            "cheap_enriched_set_id": result.candidate_set_id,
            "progress": {
                "event": "ENRICHMENT_COMPLETED",
                "candidate_count": result.candidate_count,
            },
        }

    return node


def make_select_deep_research(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        plan = deps.research_service.repository.plans[state["search_plan_id"]]
        candidates = deps.research_service.repository.get_candidates(
            state["filtered_candidate_set_id"]
        )
        criteria = _criteria(state, deps)
        evaluator = DefaultCriteriaEvaluator()
        candidates.sort(
            key=lambda v: evaluator.preference_score(v.model_dump(), criteria),
            reverse=True,
        )
        selected = [
            v.candidate_id
            for v in candidates[
                : max(plan.target_count, min(plan.candidate_target, len(candidates)))
            ]
        ]
        batches = [
            selected[i : i + plan.batch_size]
            for i in range(0, len(selected), plan.batch_size)
        ] or [[]]
        for candidate_id in selected:
            item = deps.research_service.repository.candidates[candidate_id]
            deps.research_service.repository.save_candidate(
                item.model_copy(update={"status": "SELECTED_FOR_RESEARCH"})
            )
        return {
            "deep_research_batches": batches,
            "progress": {
                "event": "DEEP_RESEARCH_STARTED",
                "candidate_count": len(selected),
            },
        }

    return node


def dispatch_deep_research(state: AgentState) -> dict:
    return {
        "progress": {
            "event": "DEEP_RESEARCH_DISPATCHED",
            "total_batches": len(state.get("deep_research_batches", [])),
        }
    }


def make_run_deep_research_batch(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        if not _execution_is_current(deps, state["research_run_id"]):
            return {"deep_research_result_refs": [_superseded_batch(deps, state["research_run_id"], "DEEP_RESEARCH")]}
        ref = asyncio.run(
            deps.research_service.deep_research_batch(
                state["research_run_id"], state.get("deep_research_batch", [])
            )
        )
        return {"deep_research_result_refs": [ref]}

    return node


def make_persist_researched_set(deps: AgentDependencies):
    def node(state: AgentState) -> dict:
        ids = []
        for ref in state.get("deep_research_result_refs", []):
            ids.extend(deps.research_service.repository.batch_results.get(ref, []))
        ids = [
            cid
            for cid in ids
            if deps.research_service.repository.candidates.get(cid)
            and deps.research_service.repository.candidates[cid].research_run_id
            == state["research_run_id"]
        ]
        result = deps.research_service.finalize(
            state["research_run_id"],
            state["filtered_candidate_set_id"],
            list(dict.fromkeys(ids)),
        )
        run = deps.research_service.repository.runs[state["research_run_id"]]
        warnings = [run.error_code] if run.error_code else []
        return {
            "candidate_set_id": result.candidate_set_id,
            "researched_candidate_set_id": result.candidate_set_id,
            "candidate_count": result.candidate_count,
            "verified_set_id": result.candidate_set_id,
            "verified_count": result.candidate_count,
            "warnings": warnings,
            "task_stage": "DISCOVERY",
            "progress": {"event": "RESEARCH_COMPLETED", "status": run.status.value},
        }

    return node
