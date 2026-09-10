from langgraph.types import Command

from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


def _invoke(graph, thread_id, text):
    return graph.invoke(
        {"session_id": thread_id, "incoming_text": text},
        config={"configurable": {"thread_id": thread_id}},
    )


def test_display_and_rank_paths_reuse_external_artifacts():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    first = _invoke(graph, "reuse-paths", "帮我找上海松江3家集团V网企业")
    tool_runs = len(deps.research_service.repository.tool_runs)
    score_count = len(deps.lead_score_repository.scores)

    display = _invoke(graph, "reuse-paths", "改成2家")
    assert display["mutation_scope"] == "DISPLAY_ONLY"
    assert len(display["lead_results"]) == 2
    assert len(deps.research_service.repository.tool_runs) == tool_runs
    assert len(deps.lead_score_repository.scores) == score_count

    rank = _invoke(graph, "reuse-paths", "物流优先")
    assert rank["mutation_scope"] == "RANK_ONLY"
    assert rank["criteria_snapshot_id"] != first["criteria_snapshot_id"]
    assert len(deps.research_service.repository.tool_runs) == tool_runs
    assert len(deps.lead_score_repository.scores) > score_count


def test_multiple_tasks_ambiguous_selection_resumes_same_thread():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    config = {"configurable": {"thread_id": "multi-task"}}
    _invoke(graph, "multi-task", "帮我找上海松江3家集团V网企业")
    group_task = deps.task_repository.get_active_task("multi-task")
    _invoke(graph, "multi-task", "再建一个上海浦东2家企业专线任务")
    dedicated_task = deps.task_repository.get_active_task("multi-task")
    assert group_task.task_id != dedicated_task.task_id
    assert len(deps.task_repository.list_tasks("multi-task")) == 2

    interrupted = _invoke(graph, "multi-task", "把那个改成1家")
    assert interrupted["__interrupt__"][0].value["type"] == "TASK_SELECTION_REQUIRED"
    resumed = graph.invoke(Command(resume={"task_id": group_task.task_id}), config=config)
    assert resumed["active_task_id"] == group_task.task_id
    assert deps.task_repository.get_task(group_task.task_id).target_count == 1
    assert len(deps.task_repository.list_tasks("multi-task")) == 2


def test_lead_query_and_export_can_target_non_active_task():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    _invoke(graph, "read-task", "帮我找上海松江3家集团V网企业")
    group_task = deps.task_repository.get_active_task("read-task")
    _invoke(graph, "read-task", "再建一个上海浦东2家企业专线任务")
    dedicated_task = deps.task_repository.get_active_task("read-task")

    query = _invoke(graph, "read-task", "为什么集团V网第1家公司评分高？")
    export = _invoke(graph, "read-task", "导出集团V网那批")
    assert query["target_task_id"] == group_task.task_id
    assert "确定性评分" in query["response_text"]
    assert export["export_spec"]["task_id"] == group_task.task_id
    assert deps.task_repository.get_active_task("read-task").task_id == dedicated_task.task_id


def test_noop_mutation_records_event_without_new_task_version():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    _invoke(graph, "noop", "帮我找上海松江3家集团V网企业")
    task = deps.task_repository.get_active_task("noop")
    version_count = len(deps.task_repository.list_versions(task.task_id))
    snapshot_count = len(deps.execution_snapshot_repository.list_for_task(task.task_id))

    result = _invoke(graph, "noop", "还是3家")

    assert result["mutation_scope"] == "NONE"
    assert len(deps.task_repository.list_versions(task.task_id)) == version_count
    assert len(deps.execution_snapshot_repository.list_for_task(task.task_id)) == snapshot_count
    assert result["mutation_id"] in deps.mutation_repository.mutations
