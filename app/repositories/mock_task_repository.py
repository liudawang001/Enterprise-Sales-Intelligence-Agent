from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from app.agent.enums import TaskStage, TaskStatus
from app.domain.task import LeadTask, TaskPatch
from app.mutation.preview import apply_patch_pure
from app.tasks.models import TaskVersion


class TaskVersionConflictError(ValueError):
    def __init__(self, task_id: str, expected: int, actual: int) -> None:
        super().__init__(f"TASK_VERSION_CONFLICT: task={task_id} expected={expected} actual={actual}")
        self.task_id = task_id
        self.expected = expected
        self.actual = actual


class MockTaskRepository:
    """In-memory versioned task repository used by the offline graph and tests."""

    def __init__(self) -> None:
        self._tasks: dict[str, LeadTask] = {}
        self._versions: dict[str, list[TaskVersion]] = {}
        self._active_by_session: dict[str, str] = {}
        self._create_requests: dict[tuple[str, str], str] = {}
        self._mutation_requests: dict[tuple[str, str], int] = {}

    def create_task(self, session_id: str, source_message_id: str | None = None) -> LeadTask:
        if source_message_id:
            existing_id = self._create_requests.get((session_id, source_message_id))
            if existing_id:
                return self.get_task(existing_id)  # type: ignore[return-value]
        task = LeadTask(
            task_id=str(uuid4()),
            session_id=session_id,
            stage=TaskStage.COLLECTING_REQUIREMENTS,
            status=TaskStatus.RUNNING,
            source_message_id=source_message_id,
        )
        self._tasks[task.task_id] = deepcopy(task)
        self._versions[task.task_id] = [TaskVersion.from_task(task)]
        self._active_by_session[session_id] = task.task_id
        if source_message_id:
            self._create_requests[(session_id, source_message_id)] = task.task_id
        return deepcopy(task)

    def get_task(self, task_id: str | None) -> LeadTask | None:
        value = self._tasks.get(task_id or "")
        return deepcopy(value) if value else None

    def get_active_task(self, session_id: str) -> LeadTask | None:
        return self.get_task(self._active_by_session.get(session_id))

    def list_tasks(self, session_id: str | None = None) -> list[LeadTask]:
        values = list(self._tasks.values())
        if session_id is not None:
            values = [task for task in values if task.session_id == session_id]
        return [deepcopy(task) for task in sorted(values, key=lambda task: task.created_at)]

    def activate_task(self, session_id: str, task_id: str) -> LeadTask:
        task = self.get_task(task_id)
        if not task or task.session_id != session_id:
            raise KeyError("TASK_NOT_FOUND")
        self._active_by_session[session_id] = task_id
        return task

    def update_task(
        self,
        task: LeadTask,
        *,
        record_version: bool = False,
        parent_version: int | None = None,
        mutation_id: str | None = None,
        source_message_id: str | None = None,
    ) -> LeadTask:
        task = task.model_copy(update={"updated_at": datetime.now(UTC)})
        self._tasks[task.task_id] = deepcopy(task)
        self._active_by_session[task.session_id] = task.task_id
        if record_version:
            versions = self._versions.setdefault(task.task_id, [])
            if not any(item.version == task.version for item in versions):
                versions.append(TaskVersion.from_task(task, parent_version=parent_version, mutation_id=mutation_id, source_message_id=source_message_id))
        return deepcopy(task)

    def assert_current(self, task_id: str, expected_version: int) -> None:
        task = self.get_task(task_id)
        if not task:
            raise KeyError("TASK_NOT_FOUND")
        if task.version != expected_version:
            raise TaskVersionConflictError(task_id, expected_version, task.version)

    def apply_patch(
        self,
        task_id: str,
        patch: TaskPatch,
        *,
        base_version: int | None = None,
        mutation_id: str | None = None,
        source_message_id: str | None = None,
    ) -> LeadTask:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"TASK_NOT_FOUND: {task_id}")
        if source_message_id:
            prior_version = self._mutation_requests.get((task_id, source_message_id))
            if prior_version is not None:
                version = self.get_version(task_id, prior_version)
                return self._task_from_version(task, version)  # type: ignore[arg-type]
        expected = task.version if base_version is None else base_version
        self.assert_current(task_id, expected)
        prospective = apply_patch_pure(task, patch)
        saved = self.update_task(prospective, record_version=True, parent_version=task.version, mutation_id=mutation_id, source_message_id=source_message_id)
        if source_message_id:
            self._mutation_requests[(task_id, source_message_id)] = saved.version
        return saved

    def set_status(self, task_id: str, *, stage: TaskStage | None = None, status: TaskStatus | None = None) -> LeadTask:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"TASK_NOT_FOUND: {task_id}")
        updates = {}
        if stage is not None:
            updates["stage"] = stage
        if status is not None:
            updates["status"] = status
        return self.update_task(task.model_copy(update=updates))

    def list_versions(self, task_id: str) -> list[TaskVersion]:
        return deepcopy(self._versions.get(task_id, []))

    def get_version(self, task_id: str, version: int) -> TaskVersion | None:
        value = next((item for item in self._versions.get(task_id, []) if item.version == version), None)
        return deepcopy(value) if value else None

    @staticmethod
    def _task_from_version(head: LeadTask, version: TaskVersion) -> LeadTask:
        return head.model_copy(update={
            "version": version.version,
            "business": version.business,
            "region": version.region,
            "target_count": version.target_count,
            "constraints": version.constraints,
            "required_fields": version.required_fields,
            "export_fields": version.export_fields,
        })

    def snapshot(self) -> dict[str, LeadTask]:
        return deepcopy(self._tasks)
