from app.agent.dependencies import build_dependencies
from app.agent.graph import build_main_graph


def test_phase_1_to_7_checkpoint_node_contract_remains_present() -> None:
    nodes = set(build_main_graph(build_dependencies()).get_graph().nodes)
    required = {
        "load_context",
        "classify_intent",
        "create_lead_task",
        "requirement",
        "business_planning",
        "research",
        "verification",
        "score_leads",
        "mutation",
        "promote_execution_snapshot",
        "compose_lead_response",
    }
    assert required <= nodes
