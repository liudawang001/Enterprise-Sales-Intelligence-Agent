from app.agent.state import AgentState


def route_intent(state: AgentState) -> str:
    return state.get("intent", "GENERAL_CHAT")
