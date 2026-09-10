from app.agent.state import AgentState


def route_more_evidence(state: AgentState) -> str:
    return (
        "TARGET"
        if state.get("unresolved_enterprise_ids")
        and state.get("verification_round", 0)
        < state.get("verification_max_rounds", 1)
        else "BUILD"
    )
