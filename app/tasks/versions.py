from app.repositories.mock_task_repository import TaskVersionConflictError


class TaskVersionFence:
    def __init__(self, repository) -> None:
        self.repository = repository

    def assert_current(self, task_id: str, expected_version: int) -> None:
        self.repository.assert_current(task_id, expected_version)


__all__ = ["TaskVersionConflictError", "TaskVersionFence"]
