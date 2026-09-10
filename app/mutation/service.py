from __future__ import annotations

from app.agent.enums import MutationScope
from app.domain.task import LeadTask, TaskPatch
from app.mutation.diff import calculate_criteria_diff
from app.mutation.models import ArtifactReuseContext, TaskMutation
from app.mutation.planner import TaskMutationPlanner
from app.mutation.preview import apply_patch_pure, build_preview, calculate_task_diff
from app.rules.models import RuleOperator
from app.rules.registry import (
    BUSINESS_CATALOG,
    RuleFieldRegistry,
    normalize_business_code,
)


class InvalidTaskPatchError(ValueError):
    pass


class MutationService:
    def __init__(self, task_repository, mutation_repository, reuse_analyzer, *, planner: TaskMutationPlanner | None = None) -> None:
        self.task_repository = task_repository
        self.repository = mutation_repository
        self.reuse_analyzer = reuse_analyzer
        self.planner = planner or TaskMutationPlanner()
        self.registry = RuleFieldRegistry()

    def validate_patch(self, patch: TaskPatch) -> TaskPatch:
        if patch.target_count is not None and patch.target_count <= 0:
            raise InvalidTaskPatchError("INVALID_TASK_PATCH: target_count must be positive")
        if patch.business is not None and normalize_business_code(patch.business) not in BUSINESS_CATALOG:
            raise InvalidTaskPatchError("INVALID_TASK_PATCH: invalid business")
        if patch.region is not None and not patch.region.strip():
            raise InvalidTaskPatchError("INVALID_TASK_PATCH: invalid region")
        for item in patch.constraints:
            definition = self.registry.get(item.field)
            if not definition:
                raise InvalidTaskPatchError(f"INVALID_TASK_PATCH: unknown field {item.field}")
            if item.operation in {"ADD", "UPDATE"}:
                if not item.operator or item.value is None:
                    raise InvalidTaskPatchError("INVALID_TASK_PATCH: constraint value and operator required")
                try:
                    operator = RuleOperator(item.operator)
                except ValueError as exc:
                    raise InvalidTaskPatchError("INVALID_TASK_PATCH: invalid operator") from exc
                if operator not in definition.allowed_operators:
                    raise InvalidTaskPatchError("INVALID_TASK_PATCH: operator is not valid for field")
            elif item.operation in {"REMOVE", "CLEAR"} and (item.operator is not None or item.value is not None):
                raise InvalidTaskPatchError("INVALID_TASK_PATCH: REMOVE/CLEAR must not include value")
        return patch

    def mutate(
        self,
        *,
        task_id: str,
        base_version: int,
        source_message_id: str,
        patch: TaskPatch,
        reuse_context: ArtifactReuseContext | None = None,
    ) -> tuple[TaskMutation, LeadTask]:
        existing = self.repository.find_mutation(task_id, source_message_id)
        if existing:
            task = self.task_repository.get_task(task_id)
            return existing, task
        self.validate_patch(patch)
        task = self.task_repository.get_task(task_id)
        if not task:
            raise KeyError("TASK_NOT_FOUND")
        self.task_repository.assert_current(task_id, base_version)
        preview = build_preview(task, patch)
        prospective = apply_patch_pure(task, patch)
        task_diff = calculate_task_diff(preview)
        criteria_diff = calculate_criteria_diff(task, prospective)
        reuse = reuse_context or self.reuse_analyzer.analyze(task_id, base_version)
        before_required = set(task.required_fields)
        newly_required = set(prospective.required_fields) - before_required if task_diff.required_fields_changed else set()
        plan = self.planner.plan(
            task_diff,
            criteria_diff,
            reuse,
            base_version=base_version,
            next_version=preview.next_version,
            before_target_count=task.target_count,
            after_target_count=prospective.target_count,
            newly_required_fields=newly_required,
        )
        mutation = TaskMutation(
            task_id=task_id,
            source_message_id=source_message_id,
            base_version=base_version,
            target_version=base_version if plan.scope == MutationScope.NONE else preview.next_version,
            patch=patch,
            preview=preview,
            task_diff=task_diff,
            criteria_diff=criteria_diff,
            scope=plan.scope,
            reexecution_plan_id=plan.plan_id,
        )
        self.repository.save_plan(plan)
        if plan.scope == MutationScope.NONE:
            self.repository.save_mutation(mutation)
            return mutation, task
        updated = self.task_repository.apply_patch(task_id, patch, base_version=base_version, mutation_id=mutation.mutation_id, source_message_id=source_message_id)
        self.repository.save_mutation(mutation)
        return mutation, updated
