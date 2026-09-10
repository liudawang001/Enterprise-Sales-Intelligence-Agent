from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.agent.subgraphs.research.nodes import build_mock_search_plan, mock_discovery, mock_enrichment, mock_verification


def build_research_graph(deps: AgentDependencies):
    builder = StateGraph(AgentState)

    def wrap(fn):
        def node(state):
            return fn({**state, "_deps": deps})
        return node

    builder.add_node("build_mock_search_plan", wrap(build_mock_search_plan))
    builder.add_node("mock_discovery", wrap(mock_discovery))
    builder.add_node("mock_enrichment", wrap(mock_enrichment))
    builder.add_node("mock_verification", wrap(mock_verification))
    builder.add_edge(START, "build_mock_search_plan")
    builder.add_edge("build_mock_search_plan", "mock_discovery")
    builder.add_edge("mock_discovery", "mock_enrichment")
    builder.add_edge("mock_enrichment", "mock_verification")
    builder.add_edge("mock_verification", END)
    return builder.compile()
