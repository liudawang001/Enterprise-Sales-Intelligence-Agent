from app.agent.dependencies import build_dependencies
from app.agent.enums import MutationScope
from app.agent.routers.mutation_router import route_mutation


def test_mutation_scope_for_count_reduction_and_business_change():
    deps = build_dependencies()
    task = deps.task_repository.create_task("mutation-1")
    task.target_count = 50
    deps.task_repository.update_task(task)
    assert deps.task_service.classify_mutation("数量改30", task)[0] == MutationScope.DISPLAY_ONLY
    assert deps.task_service.classify_mutation("改成企业专线", task)[0] == MutationScope.FULL_REPLAN
    assert route_mutation({"mutation_scope": MutationScope.FULL_REPLAN}) == MutationScope.FULL_REPLAN


def test_mutation_updates_task_version():
    deps = build_dependencies()
    task = deps.task_repository.create_task("mutation-version")
    task.target_count = 50
    deps.task_repository.update_task(task)
    updated = deps.task_service.apply_patch(task.task_id, deps.task_service.parse_mutation("数量改成30家"))
    assert updated.target_count == 30
    assert updated.version == task.version + 1
