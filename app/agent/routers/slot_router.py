from app.agent.state import AgentState


def route_missing_slots(state: AgentState) -> str:
    return "MISSING" if state.get("missing_slots") else "COMPLETE"
