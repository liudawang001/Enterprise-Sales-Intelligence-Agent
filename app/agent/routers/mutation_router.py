from app.agent.state import AgentState


def route_mutation(state: AgentState) -> str:
    return state.get("mutation_scope", "FULL_REPLAN")
