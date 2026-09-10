from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.agent.enums import TaskStage, TaskStatus
from app.domain.task import LeadTask, TaskPatch


class MockTaskRepository:
    """In-memory repository with the same boundary as a future Postgres adapter."""

    def __init__(self) -> None:
        self._tasks: dict[str, LeadTask] = {}
        self._active_by_session: dict[str, str] = {}

    def create_task(self, session_id: str) -> LeadTask:
        existing = self.get_active_task(session_id)
        if existing is not None:
            return deepcopy(existing)
        task = LeadTask(
            task_id=str(uuid4()),
            session_id=session_id,
            stage=TaskStage.COLLECTING_REQUIREMENTS,
            status=TaskStatus.RUNNING,
        )
        self._tasks[task.task_id] = task
        self._active_by_session[session_id] = task.task_id
        return deepcopy(task)

    def get_task(self, task_id: str | None) -> LeadTask | None:
        if not task_id or task_id not in self._tasks:
            return None
        return deepcopy(self._tasks[task_id])

    def get_active_task(self, session_id: str) -> LeadTask | None:
        task_id = self._active_by_session.get(session_id)
        return self.get_task(task_id)

    def update_task(self, task: LeadTask) -> LeadTask:
        self._tasks[task.task_id] = deepcopy(task)
        self._active_by_session[task.session_id] = task.task_id
        return deepcopy(task)

    def apply_patch(self, task_id: str, patch: TaskPatch) -> LeadTask:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        values = patch.model_dump(exclude_none=True)
        for field in ("business", "region", "target_count"):
            if field in values:
                setattr(task, field, values[field])
        for constraint in patch.constraints:
            item = constraint.model_dump(exclude_none=True)
            field = item["field"]
            operation = item["operation"]
            existing = [c for c in task.constraints if c.get("field") != field]
            if operation not in {"REMOVE", "CLEAR"}:
                existing.append({k: v for k, v in item.items() if k != "operation"})
            task.constraints = existing
        task.version += 1
        return self.update_task(task)

    def set_status(self, task_id: str, *, stage: TaskStage | None = None, status: TaskStatus | None = None) -> LeadTask:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        if stage is not None:
            task.stage = stage
        if status is not None:
            task.status = status
        return self.update_task(task)

    def snapshot(self) -> dict[str, LeadTask]:
        return deepcopy(self._tasks)
