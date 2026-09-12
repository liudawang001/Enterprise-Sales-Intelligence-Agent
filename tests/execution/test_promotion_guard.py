from app.execution.models import ArtifactValidity, TaskExecutionSnapshot
from app.execution.repository import InMemoryExecutionSnapshotRepository


def test_stale_execution_is_saved_but_cannot_promote():
    repository = InMemoryExecutionSnapshotRepository()
    current = TaskExecutionSnapshot(task_id="task", task_version=5, lead_score_set_id="score-5")
    stale = TaskExecutionSnapshot(task_id="task", task_version=4, lead_score_set_id="score-4")

    assert repository.promote(current, current_task_version=5)
    assert not repository.promote(stale, current_task_version=5)
    assert repository.current("task").lead_score_set_id == "score-5"
    assert repository.get(stale.snapshot_id).validity == ArtifactValidity.SUPERSEDED
