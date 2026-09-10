from app.agent.dependencies import build_dependencies
from app.agent.subgraphs.requirement.graph import build_requirement_graph


def test_complete_requirement_does_not_interrupt():
    deps = build_dependencies()
    task = deps.task_repository.create_task("complete-1")
    graph = build_requirement_graph(deps)
    result = graph.invoke(
        {
            "active_task_id": task.task_id,
            "incoming_text": "帮我找上海松江50家集团V网客户",
        }
    )
    assert "__interrupt__" not in result
    task = deps.task_repository.get_active_task("complete-1")
    assert task is not None
    assert task.business == "集团V网"
    assert task.region == "上海松江"
    assert task.target_count == 50
    assert task.version >= 2
