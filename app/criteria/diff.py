from collections import defaultdict

from app.criteria.models import CriteriaDiff, LeadCriteria


def _key(item) -> tuple:
    return item.field, item.operator.value, repr(item.value)


def _split_changes(old_items, new_items):
    old_by_field = defaultdict(list)
    new_by_field = defaultdict(list)
    for item in old_items:
        old_by_field[item.field].append(item)
    for item in new_items:
        new_by_field[item.field].append(item)
    added, removed, changed = [], [], []
    for field in sorted(set(old_by_field) | set(new_by_field)):
        old_group, new_group = old_by_field[field], new_by_field[field]
        if old_group and new_group and {_key(x) for x in old_group} != {_key(x) for x in new_group}:
            changed.append({"field": field, "before": [x.model_dump(mode="json") for x in old_group], "after": [x.model_dump(mode="json") for x in new_group]})
        elif not old_group:
            added.extend(new_group)
        elif not new_group:
            removed.extend(old_group)
    return added, removed, changed


def diff_criteria(old: LeadCriteria, new: LeadCriteria) -> CriteriaDiff:
    added_hard, removed_hard, changed_hard = _split_changes(old.hard_constraints, new.hard_constraints)
    added_soft, removed_soft, changed_soft = _split_changes(old.ranking_preferences, new.ranking_preferences)
    return CriteriaDiff(added_hard=added_hard, removed_hard=removed_hard, changed_hard=changed_hard, added_soft=added_soft, removed_soft=removed_soft, changed_soft=changed_soft, business_changed=old.business_code != new.business_code, region_changed=old.region_scope != new.region_scope, target_count_changed=old.target_count != new.target_count)

