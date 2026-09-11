from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


def _invoke(graph, thread_id: str, text: str):
    return graph.invoke(
        {"session_id": thread_id, "incoming_text": text},
        config={"configurable": {"thread_id": thread_id}},
    )


def test_delivery_snapshot_freezes_current_projection():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    _invoke(graph, "delivery-freeze", "帮我找上海松江3家集团V网企业")
    task = deps.task_repository.get_active_task("delivery-freeze")

    frozen = deps.delivery_query_service.freeze(task.task_id, task.version)
    original = frozen.leads[0]
    enterprise = deps.enterprise_repository.enterprises[original.enterprise_id]
    deps.enterprise_repository.enterprises[original.enterprise_id] = enterprise.model_copy(
        update={"canonical_name": "不应进入快照的新名称"}
    )

    reread = deps.delivery_query_service.get_bundle(frozen.snapshot.snapshot_id)
    assert reread.leads[0].enterprise_name == original.enterprise_name
    assert reread.snapshot.task_version == task.version
    assert reread.snapshot.lead_score_set_id
    assert reread.snapshot.verified_lead_set_id


def test_delivery_reads_historical_version_and_paginates_globally():
    deps = build_dependencies()
    graph = build_main_graph(deps)
    _invoke(graph, "delivery-history", "帮我找上海松江3家集团V网企业")
    task = deps.task_repository.get_active_task("delivery-history")
    historical_version = task.version
    historical = deps.delivery_query_service.freeze(task.task_id, historical_version)

    _invoke(graph, "delivery-history", "改成2家")
    current = deps.task_repository.get_task(task.task_id)
    page = deps.delivery_query_service.lead_page(
        task.task_id, historical_version, page=2, page_size=1
    )

    assert current.version > historical_version
    assert historical.task.historical is False
    refreshed = deps.delivery_query_service.freeze(task.task_id, historical_version)
    assert refreshed.snapshot.snapshot_id == historical.snapshot.snapshot_id
    assert page.items[0].rank == 2
    assert page.task_version == historical_version
