from __future__ import annotations

from copy import deepcopy

from app.execution.models import ArtifactValidity, TaskExecutionSnapshot


class InMemoryExecutionSnapshotRepository:
    def __init__(self) -> None:
        self.snapshots: dict[str, TaskExecutionSnapshot] = {}
        self._current: dict[str, str] = {}

    def save(self, value: TaskExecutionSnapshot) -> TaskExecutionSnapshot:
        self.snapshots[value.snapshot_id] = deepcopy(value)
        return deepcopy(value)

    def get(self, snapshot_id: str | None) -> TaskExecutionSnapshot | None:
        value = self.snapshots.get(snapshot_id or "")
        return deepcopy(value) if value else None

    def current(self, task_id: str) -> TaskExecutionSnapshot | None:
        return self.get(self._current.get(task_id))

    def for_version(self, task_id: str, version: int) -> TaskExecutionSnapshot | None:
        values = [value for value in self.snapshots.values() if value.task_id == task_id and value.task_version == version]
        return deepcopy(values[-1]) if values else None

    def list_for_task(self, task_id: str) -> list[TaskExecutionSnapshot]:
        return [deepcopy(value) for value in self.snapshots.values() if value.task_id == task_id]

    def promote(self, value: TaskExecutionSnapshot, *, current_task_version: int) -> bool:
        if value.task_version != current_task_version:
            self.save(value.model_copy(update={"is_current": False, "validity": ArtifactValidity.SUPERSEDED}))
            return False
        previous = self.current(value.task_id)
        if previous:
            self.save(previous.model_copy(update={"is_current": False, "validity": ArtifactValidity.REUSABLE}))
        promoted = value.model_copy(update={"is_current": True, "validity": ArtifactValidity.CURRENT})
        self.save(promoted)
        self._current[value.task_id] = value.snapshot_id
        return True
