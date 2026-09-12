from app.domain.task import TaskPatch
from app.repositories.mock_task_repository import MockTaskRepository
from app.tasks.references import TaskReferenceResolver


def _tasks():
    repository = MockTaskRepository()
    group = repository.create_task("thread", "group")
    group = repository.apply_patch(group.task_id, TaskPatch(business="集团V网", region="上海松江", target_count=50), base_version=1)
    dedicated = repository.create_task("thread", "dedicated")
    dedicated = repository.apply_patch(dedicated.task_id, TaskPatch(business="企业专线", region="上海浦东", target_count=20), base_version=1)
    return repository, group, dedicated


def test_business_name_resolves_non_active_task():
    repository, group, dedicated = _tasks()
    resolver = TaskReferenceResolver(repository)
    reference = resolver.parse("把集团V网那个改成30家", active_task_id=dedicated.task_id)
    result = resolver.resolve("thread", reference, active_task_id=dedicated.task_id)
    assert result.status == "RESOLVED"
    assert result.task_id == group.task_id


def test_vague_reference_with_multiple_tasks_is_ambiguous_without_active_context():
    repository, _, _ = _tasks()
    resolver = TaskReferenceResolver(repository)
    result = resolver.resolve("thread", resolver.parse("把那个改成30家"))
    assert result.status == "AMBIGUOUS"
    assert len(result.candidates) == 2
