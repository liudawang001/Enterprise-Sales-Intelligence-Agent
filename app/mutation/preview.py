from copy import deepcopy

from app.domain.task import LeadTask, TaskPatch
from app.mutation.models import MutationPreview, TaskDiff


def apply_patch_pure(task: LeadTask, patch: TaskPatch) -> LeadTask:
    prospective = task.model_copy(deep=True)
    values = patch.model_dump(exclude_none=True)
    for field in ("business", "region", "target_count", "required_fields", "export_fields"):
        if field in values:
            setattr(prospective, field, deepcopy(values[field]))
    for constraint in patch.constraints:
        item = constraint.model_dump(exclude_none=True)
        existing = [value for value in prospective.constraints if value.get("field") != constraint.field]
        if constraint.operation not in {"REMOVE", "CLEAR"}:
            existing.append({key: value for key, value in item.items() if key != "operation"})
        prospective.constraints = existing
    prospective.version = task.version + 1
    return prospective


def build_preview(task: LeadTask, patch: TaskPatch) -> MutationPreview:
    prospective = apply_patch_pure(task, patch)
    fields = {"business", "region", "target_count", "constraints", "required_fields", "export_fields"}
    return MutationPreview(
        task_id=task.task_id,
        base_version=task.version,
        next_version=prospective.version,
        before=task.model_dump(mode="json", include=fields),
        after=prospective.model_dump(mode="json", include=fields),
        patch=patch,
    )


def calculate_task_diff(preview: MutationPreview) -> TaskDiff:
    before, after = preview.before, preview.after
    before_by_field = {item["field"]: item for item in before.get("constraints", [])}
    after_by_field = {item["field"]: item for item in after.get("constraints", [])}
    changed = sorted(field for field in set(before_by_field) | set(after_by_field) if before_by_field.get(field) != after_by_field.get(field))
    changed_values = [before_by_field.get(field) or after_by_field.get(field) or {} for field in changed]
    return TaskDiff(
        business_changed=before.get("business") != after.get("business"),
        region_changed=before.get("region") != after.get("region"),
        target_count_changed=before.get("target_count") != after.get("target_count"),
        required_fields_changed=before.get("required_fields", []) != after.get("required_fields", []),
        export_fields_changed=before.get("export_fields", []) != after.get("export_fields", []),
        constraint_fields_changed=changed,
        hard_constraints_changed=any(item.get("constraint_type", "HARD") == "HARD" for item in changed_values),
        soft_constraints_changed=any(item.get("constraint_type") == "SOFT" for item in changed_values),
    )
