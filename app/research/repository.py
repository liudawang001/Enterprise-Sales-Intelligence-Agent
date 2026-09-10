from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from app.research.models import (
    CandidateSet,
    RawEnterpriseCandidate,
    ResearchBatch,
    ResearchRun,
    SearchPlan,
    SourceRecord,
    ToolRun,
)


class InMemoryResearchRepository:
    def __init__(self) -> None:
        self.runs: dict[str, ResearchRun] = {}
        self.plans: dict[str, SearchPlan] = {}
        self.candidates: dict[str, RawEnterpriseCandidate] = {}
        self.candidate_sets: dict[str, CandidateSet] = {}
        self.sources: dict[str, SourceRecord] = {}
        self.tool_runs: dict[str, ToolRun] = {}
        self.batch_results: dict[str, list[str]] = {}
        self.batches: dict[str, ResearchBatch] = {}
        self.events: dict[str, list[dict]] = {}

    def save_run(self, value: ResearchRun) -> ResearchRun:
        self.runs[value.research_run_id] = deepcopy(value)
        return deepcopy(value)

    def save_plan(self, value: SearchPlan) -> SearchPlan:
        self.plans[value.plan_id] = deepcopy(value)
        return deepcopy(value)

    def save_candidate(self, value: RawEnterpriseCandidate) -> RawEnterpriseCandidate:
        self.candidates[value.candidate_id] = deepcopy(value)
        return deepcopy(value)

    def save_source(self, value: SourceRecord) -> SourceRecord:
        self.sources[value.source_record_id] = deepcopy(value)
        return deepcopy(value)

    def save_candidate_set(self, value: CandidateSet) -> CandidateSet:
        value = value.model_copy(update={"candidate_count": len(value.candidate_ids)})
        self.candidate_sets[value.candidate_set_id] = deepcopy(value)
        return deepcopy(value)

    def save_tool_run(self, value: ToolRun) -> ToolRun:
        self.tool_runs[value.tool_run_id] = deepcopy(value)
        return deepcopy(value)

    def find_successful_tool_run(
        self, request_hash: str, max_age_seconds: int | None = None
    ) -> ToolRun | None:
        match = next(
            (
                v
                for v in self.tool_runs.values()
                if v.request_hash == request_hash and v.status == "SUCCESS"
            ),
            None,
        )
        if (
            match
            and max_age_seconds is not None
            and (datetime.now(UTC) - match.finished_at).total_seconds()
            > max_age_seconds
        ):
            return None
        return deepcopy(match)

    def get_run_for_task(self, task_id: str) -> ResearchRun | None:
        values = [v for v in self.runs.values() if v.task_id == task_id]
        return deepcopy(values[-1]) if values else None

    def get_candidates(
        self, candidate_set_id: str | None
    ) -> list[RawEnterpriseCandidate]:
        item = self.candidate_sets.get(candidate_set_id or "")
        return (
            [
                deepcopy(self.candidates[cid])
                for cid in item.candidate_ids
                if cid in self.candidates
            ]
            if item
            else []
        )

    def get_candidate(self, candidate_id: str) -> RawEnterpriseCandidate | None:
        return deepcopy(self.candidates.get(candidate_id))

    def get_sources(self, candidate_id: str) -> list[SourceRecord]:
        return [
            deepcopy(v) for v in self.sources.values() if v.candidate_id == candidate_id
        ]

    def save_batch_result(
        self,
        batch_id: str,
        candidate_ids: list[str],
        *,
        research_run_id: str = "",
        stage: str = "",
        query_ids: list[str] | None = None,
    ) -> str:
        self.batch_results[batch_id] = list(candidate_ids)
        self.batches[batch_id] = ResearchBatch(
            batch_id=batch_id,
            research_run_id=research_run_id,
            stage=stage,
            candidate_ids=list(candidate_ids),
            query_ids=query_ids or [],
        )
        return batch_id

    def record_event(self, research_run_id: str, event: str, **data: object) -> None:
        self.events.setdefault(research_run_id, []).append({"event": event, **data})
