from __future__ import annotations

from dataclasses import dataclass

from app.agent.enums import MutationScope
from app.criteria.models import CompiledConstraint, CriteriaDiff, RankingPreference
from app.domain.task import TaskPatch
from app.execution.models import ArtifactValidity, TaskExecutionSnapshot
from app.execution.repository import InMemoryExecutionSnapshotRepository
from app.mutation.models import ArtifactReuseContext, TaskDiff
from app.mutation.planner import TaskMutationPlanner
from app.repositories.mock_task_repository import (
    MockTaskRepository,
    TaskVersionConflictError,
)


@dataclass
class MutationEvalReport:
    scope_case_count: int
    reuse_case_count: int
    version_case_count: int
    mutation_scope_accuracy: float
    unsafe_under_reexecution_rate: float
    unnecessary_full_replan_rate: float
    artifact_reuse_correctness: float
    version_fence_correctness: float
    mutation_idempotency: float


def _context(**updates) -> ArtifactReuseContext:
    values = {
        "task_id": "task-eval",
        "task_version": 4,
        "criteria_snapshot_id": "criteria-4",
        "search_plan_id": "plan-4",
        "raw_candidate_set_id": "raw-4",
        "raw_candidate_count": 120,
        "filtered_candidate_set_id": "filtered-4",
        "filtered_candidate_count": 90,
        "researched_candidate_set_id": "researched-4",
        "researched_candidate_count": 80,
        "verified_lead_set_id": "verified-4",
        "verified_lead_count": 80,
        "lead_score_set_id": "scores-4",
        "scored_lead_count": 50,
        "available_candidate_fields": {"industry", "employee_count", "region"},
        "available_verified_fields": {"industry", "employee_count", "website"},
        "discovery_pushdown_fields": {"industry"},
        "post_filter_fields": {"employee_count"},
        "enrichment_fields": {"website", "employee_count", "public_phone"},
        "field_dependencies": {"region": ["DISCOVERY"], "industry": ["DISCOVERY", "RANK"], "employee_count": ["FILTER"], "website": ["ENRICHMENT"]},
    }
    values.update(updates)
    return ArtifactReuseContext(**values)


def build_scope_cases() -> list[dict]:
    cases = []

    def add(name, task_diff, criteria_diff, expected, *, context=None, before=50, after=50, required=None):
        cases.append({
            "name": name,
            "before_task": {"target_count": before},
            "after_task": {"target_count": after},
            "patch": {"target_count": after} if before != after else {},
            "before_criteria": criteria_diff.model_dump(mode="json"),
            "before_search_plan": (context or _context()).field_dependencies,
            "candidate_counts": {"raw": (context or _context()).raw_candidate_count, "verified": (context or _context()).verified_lead_count, "scored": (context or _context()).scored_lead_count},
            "available_candidate_fields": sorted((context or _context()).available_candidate_fields),
            "available_verified_fields": sorted((context or _context()).available_verified_fields),
            "task_diff": task_diff,
            "criteria_diff": criteria_diff,
            "context": context or _context(),
            "before": before,
            "after": after,
            "required": required or set(),
            "expected_scope": expected,
        })

    for index, after in enumerate(range(10, 20)):
        add(f"target-decrease-{index}", TaskDiff(target_count_changed=True), CriteriaDiff(target_count_changed=True), MutationScope.DISPLAY_ONLY, before=50, after=after)
    for index, after in enumerate(range(51, 61)):
        add(f"within-score-{index}", TaskDiff(target_count_changed=True), CriteriaDiff(target_count_changed=True), MutationScope.DISPLAY_ONLY, context=_context(scored_lead_count=80), before=50, after=after)
    for index, after in enumerate(range(61, 66)):
        add(f"within-verified-{index}", TaskDiff(target_count_changed=True), CriteriaDiff(target_count_changed=True), MutationScope.RANK_ONLY, before=50, after=after)
    for index, after in enumerate(range(200, 205)):
        add(f"universe-insufficient-{index}", TaskDiff(target_count_changed=True), CriteriaDiff(target_count_changed=True), MutationScope.DISCOVERY_REQUIRED, before=50, after=after)
    for index in range(5):
        add(f"region-{index}", TaskDiff(region_changed=True), CriteriaDiff(region_changed=True), MutationScope.DISCOVERY_REQUIRED)
        add(f"business-{index}", TaskDiff(business_changed=True), CriteriaDiff(business_changed=True), MutationScope.FULL_REPLAN)
    employee = CompiledConstraint(field="employee_count", operator="GTE", value=100)
    industry = CompiledConstraint(field="industry", operator="EQ", value="制造业")
    soft = RankingPreference(field="industry", operator="EQ", value="物流", normalized_weight=1)
    for index in range(5):
        add(f"post-filter-removal-{index}", TaskDiff(constraint_fields_changed=["employee_count"], hard_constraints_changed=True), CriteriaDiff(removed_hard=[employee]), MutationScope.FILTER_ONLY)
        add(f"pushdown-removal-{index}", TaskDiff(constraint_fields_changed=["industry"], hard_constraints_changed=True), CriteriaDiff(removed_hard=[industry]), MutationScope.DISCOVERY_REQUIRED)
        add(f"soft-covered-{index}", TaskDiff(constraint_fields_changed=["industry"], soft_constraints_changed=True), CriteriaDiff(added_soft=[soft]), MutationScope.RANK_ONLY)
        add(f"soft-missing-{index}", TaskDiff(constraint_fields_changed=["industry"], soft_constraints_changed=True), CriteriaDiff(added_soft=[soft]), MutationScope.ENRICHMENT_REQUIRED, context=_context(available_verified_fields={"website"}))
    return cases


def run_evaluation() -> MutationEvalReport:
    planner = TaskMutationPlanner()
    cases = build_scope_cases()
    correct = 0
    unsafe = 0
    unnecessary_full = 0
    severity = {MutationScope.NONE: 0, MutationScope.DISPLAY_ONLY: 1, MutationScope.RANK_ONLY: 2, MutationScope.FILTER_ONLY: 3, MutationScope.ENRICHMENT_REQUIRED: 4, MutationScope.DISCOVERY_REQUIRED: 5, MutationScope.FULL_REPLAN: 6}
    for case in cases:
        plan = planner.plan(case["task_diff"], case["criteria_diff"], case["context"], base_version=4, next_version=5, before_target_count=case["before"], after_target_count=case["after"], newly_required_fields=case["required"])
        correct += plan.scope == case["expected_scope"]
        unsafe += severity[plan.scope] < severity[case["expected_scope"]]
        unnecessary_full += plan.scope == MutationScope.FULL_REPLAN and case["expected_scope"] != MutationScope.FULL_REPLAN

    reuse_correct = 0
    reuse_cases = 20
    for index in range(reuse_cases):
        scope_diff = TaskDiff(target_count_changed=True) if index < 10 else TaskDiff(constraint_fields_changed=["industry"], soft_constraints_changed=True)
        criteria_diff = CriteriaDiff(target_count_changed=True) if index < 10 else CriteriaDiff(added_soft=[RankingPreference(field="industry", operator="EQ", value="物流", normalized_weight=1)])
        after = 30 if index < 10 else 50
        plan = planner.plan(scope_diff, criteria_diff, _context(scored_lead_count=80), base_version=4, next_version=5, before_target_count=50, after_target_count=after)
        expected = {"criteria-4", "plan-4", "raw-4", "filtered-4", "researched-4", "verified-4", "scores-4"} if index < 10 else {"plan-4", "raw-4", "filtered-4", "researched-4", "verified-4"}
        reuse_correct += set(plan.reused_artifact_ids) == expected

    fence_correct = 0
    idempotency_correct = 0
    version_cases = 20
    for index in range(10):
        tasks = MockTaskRepository()
        task = tasks.create_task(f"thread-{index}")
        tasks.apply_patch(task.task_id, TaskPatch(target_count=50), base_version=1, source_message_id="first")
        try:
            tasks.apply_patch(task.task_id, TaskPatch(target_count=30), base_version=1, source_message_id="stale")
        except TaskVersionConflictError:
            fence_correct += 1
        duplicate = tasks.apply_patch(task.task_id, TaskPatch(target_count=20), base_version=2, source_message_id="same")
        replay = tasks.apply_patch(task.task_id, TaskPatch(target_count=10), base_version=2, source_message_id="same")
        idempotency_correct += duplicate.version == replay.version and len(tasks.list_versions(task.task_id)) == 3
    for index in range(10):
        snapshots = InMemoryExecutionSnapshotRepository()
        current = TaskExecutionSnapshot(task_id=f"task-{index}", task_version=5)
        stale = TaskExecutionSnapshot(task_id=f"task-{index}", task_version=4)
        snapshots.promote(current, current_task_version=5)
        rejected = not snapshots.promote(stale, current_task_version=5)
        fence_correct += rejected and snapshots.get(stale.snapshot_id).validity == ArtifactValidity.SUPERSEDED and snapshots.current(current.task_id).task_version == 5

    return MutationEvalReport(
        scope_case_count=len(cases),
        reuse_case_count=reuse_cases,
        version_case_count=version_cases,
        mutation_scope_accuracy=correct / len(cases),
        unsafe_under_reexecution_rate=unsafe / len(cases),
        unnecessary_full_replan_rate=unnecessary_full / len(cases),
        artifact_reuse_correctness=reuse_correct / reuse_cases,
        version_fence_correctness=fence_correct / version_cases,
        mutation_idempotency=idempotency_correct / 10,
    )


if __name__ == "__main__":
    report = run_evaluation()
    for key, value in report.__dict__.items():
        print(f"{key}: {value}")
