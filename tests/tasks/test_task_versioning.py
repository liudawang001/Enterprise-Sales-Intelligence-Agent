import pytest

from app.domain.task import TaskPatch
from app.repositories.mock_task_repository import (
    MockTaskRepository,
    TaskVersionConflictError,
)


def test_task_versions_are_immutable_and_mutation_is_idempotent():
    repository = MockTaskRepository()
    task = repository.create_task("thread-1", "create-1")
    updated = repository.apply_patch(task.task_id, TaskPatch(business="集团V网", region="上海松江", target_count=50), base_version=1, mutation_id="00000000-0000-0000-0000-000000000001", source_message_id="message-1")
    duplicate = repository.apply_patch(task.task_id, TaskPatch(target_count=30), base_version=1, mutation_id="00000000-0000-0000-0000-000000000002", source_message_id="message-1")

    assert updated.version == 2
    assert duplicate.version == 2
    assert duplicate.target_count == 50
    assert [value.version for value in repository.list_versions(task.task_id)] == [1, 2]
    assert repository.get_version(task.task_id, 1).target_count is None


def test_stale_base_version_is_rejected_without_creating_version():
    repository = MockTaskRepository()
    task = repository.create_task("thread-1")
    repository.apply_patch(task.task_id, TaskPatch(target_count=50), base_version=1)

    with pytest.raises(TaskVersionConflictError, match="TASK_VERSION_CONFLICT"):
        repository.apply_patch(task.task_id, TaskPatch(target_count=30), base_version=1)

    assert len(repository.list_versions(task.task_id)) == 2


def test_one_thread_can_own_multiple_tasks_and_switch_active_task():
    repository = MockTaskRepository()
    first = repository.create_task("thread-1", "create-1")
    second = repository.create_task("thread-1", "create-2")

    assert len(repository.list_tasks("thread-1")) == 2
    assert repository.get_active_task("thread-1").task_id == second.task_id
    repository.activate_task("thread-1", first.task_id)
    assert repository.get_active_task("thread-1").task_id == first.task_id
