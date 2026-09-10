from __future__ import annotations

import re

from app.rules.registry import BUSINESS_CATALOG, normalize_business_code
from app.tasks.models import (
    TaskCandidate,
    TaskReference,
    TaskReferenceResolution,
    TaskReferenceStatus,
)


class TaskReferenceResolver:
    """Resolve a conversation reference without guessing between valid tasks."""

    def __init__(self, repository) -> None:
        self.repository = repository

    @staticmethod
    def parse(text: str, *, active_task_id: str | None = None) -> TaskReference:
        explicit = re.search(
            r"(?:task[_-]?id|任务ID)[:=\s]*([0-9a-fA-F-]{8,}|task[_-][\w-]+)",
            text,
            re.IGNORECASE,
        )
        business_hint = None
        for code, item in BUSINESS_CATALOG.items():
            if any(alias in text for alias in [item["name"], *item["aliases"]]):
                business_hint = code
                break
        ordinal = next(
            (value for value in ("刚才", "上一个", "最近", "第一个", "第二个") if value in text),
            None,
        )
        vague = bool(re.search(r"(?:那个|这个|当前任务|现在这个)", text))
        return TaskReference(
            explicit_task_id=explicit.group(1) if explicit else None,
            business_hint=business_hint,
            ordinal_hint=ordinal,
            use_active_task=bool(active_task_id and (vague or not business_hint)),
            confidence=1.0 if explicit or business_hint else 0.65 if active_task_id else 0.0,
        )

    def resolve(
        self,
        session_id: str,
        reference: TaskReference,
        *,
        active_task_id: str | None = None,
    ) -> TaskReferenceResolution:
        tasks = self.repository.list_tasks(session_id)
        candidates = [TaskCandidate(task_id=t.task_id, business=t.business, region=t.region, version=t.version) for t in tasks]
        if reference.explicit_task_id:
            task = self.repository.get_task(reference.explicit_task_id)
            if task and task.session_id == session_id:
                return TaskReferenceResolution(status=TaskReferenceStatus.RESOLVED, task_id=task.task_id, reference=reference, candidates=[TaskCandidate(task_id=task.task_id, business=task.business, region=task.region, version=task.version)], reason="EXPLICIT_TASK_ID")
            return TaskReferenceResolution(status=TaskReferenceStatus.NOT_FOUND, reference=reference, reason="TASK_NOT_FOUND")
        if reference.business_hint:
            matches = [task for task in tasks if task.business and normalize_business_code(task.business) == reference.business_hint]
            if len(matches) == 1:
                return TaskReferenceResolution(status=TaskReferenceStatus.RESOLVED, task_id=matches[0].task_id, reference=reference, candidates=[TaskCandidate(task_id=matches[0].task_id, business=matches[0].business, region=matches[0].region, version=matches[0].version)], reason="UNIQUE_BUSINESS_MATCH")
            if len(matches) > 1:
                candidates = [TaskCandidate(task_id=t.task_id, business=t.business, region=t.region, version=t.version) for t in matches]
                return TaskReferenceResolution(status=TaskReferenceStatus.AMBIGUOUS, reference=reference, candidates=candidates, reason="BUSINESS_MATCH_AMBIGUOUS")
        if reference.use_active_task and active_task_id:
            task = self.repository.get_task(active_task_id)
            if task and task.session_id == session_id:
                return TaskReferenceResolution(status=TaskReferenceStatus.RESOLVED, task_id=task.task_id, reference=reference, candidates=[TaskCandidate(task_id=task.task_id, business=task.business, region=task.region, version=task.version)], reason="ACTIVE_TASK")
        if len(tasks) == 1:
            return TaskReferenceResolution(status=TaskReferenceStatus.RESOLVED, task_id=tasks[0].task_id, reference=reference, candidates=candidates, reason="ONLY_COMPATIBLE_TASK")
        if reference.ordinal_hint in {"刚才", "上一个", "最近"} and tasks:
            latest = max(tasks, key=lambda task: task.updated_at)
            return TaskReferenceResolution(status=TaskReferenceStatus.RESOLVED, task_id=latest.task_id, reference=reference, candidates=[TaskCandidate(task_id=latest.task_id, business=latest.business, region=latest.region, version=latest.version)], reason="MOST_RECENT_TASK")
        return TaskReferenceResolution(status=TaskReferenceStatus.AMBIGUOUS if tasks else TaskReferenceStatus.NOT_FOUND, reference=reference, candidates=candidates, reason="TASK_REFERENCE_AMBIGUOUS" if tasks else "TASK_NOT_FOUND")
