from app.agent.dependencies import build_dependencies
from app.agent.subgraphs.requirement.graph import build_requirement_graph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


def test_interrupt_and_resume_same_thread_without_new_task():
    deps = build_dependencies()
    task = deps.task_repository.create_task("resume-1")
    graph = build_requirement_graph(deps, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "resume-1"}}
    first = graph.invoke(
        {"active_task_id": task.task_id, "incoming_text": "帮我找集团V网客户"},
        config=config,
    )
    assert first["__interrupt__"]
    task_before = deps.task_repository.get_active_task("resume-1")
    assert task_before is not None
    resumed = graph.invoke(Command(resume={"text": "上海松江，50家"}), config=config)
    task_after = deps.task_repository.get_active_task("resume-1")
    assert "__interrupt__" not in resumed
    assert task_after is not None
    assert task_after.task_id == task_before.task_id
    assert task_after.business == "集团V网"
    assert task_after.region == "上海松江"
    assert task_after.target_count == 50
    assert resumed["task_status"] == "RUNNING"
