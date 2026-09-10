from app.agent.dependencies import build_dependencies
from app.agent.subgraphs.business_planning.graph import build_business_planning_graph
from app.agent.subgraphs.business_qa.graph import build_business_qa_graph
from app.agent.subgraphs.mutation.graph import build_mutation_graph
from app.agent.subgraphs.research.graph import build_research_graph
from app.domain.task import TaskPatch


def _complete_task(deps, session_id: str):
    task = deps.task_repository.create_task(session_id)
    return deps.task_repository.apply_patch(
        task.task_id,
        TaskPatch(business="集团V网", region="上海松江", target_count=50),
    )


def test_business_qa_and_planning_subgraphs() -> None:
    deps = build_dependencies()
    task = _complete_task(deps, "subgraph-planning")

    qa = build_business_qa_graph().invoke({"incoming_text": "集团V网是什么？"})
    planning = build_business_planning_graph(deps).invoke({"active_task_id": task.task_id})

    assert "没有找到足够证据" in qa["response_text"]
    assert planning["criteria_snapshot_id"]


def test_research_and_mutation_subgraphs() -> None:
    deps = build_dependencies()
    task = _complete_task(deps, "subgraph-research")

    research = build_research_graph(deps).invoke({"active_task_id": task.task_id})
    mutation = build_mutation_graph(deps).invoke(
        {"active_task_id": task.task_id, "incoming_text": "数量改成30家"}
    )

    assert research["candidate_count"] == 5
    assert research["verified_count"] == 5
    assert mutation["mutation_scope"] == "DISPLAY_ONLY"
    assert mutation["task_version"] == task.version + 1
