from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.agent.subgraphs.business_planning.nodes import build_mock_criteria, load_mock_business_context


def build_business_planning_graph(deps: AgentDependencies):
    builder = StateGraph(AgentState)

    def wrap(fn):
        def node(state):
            return fn({**state, "_deps": deps})
        return node

    builder.add_node("load_mock_business_context", wrap(load_mock_business_context))
    builder.add_node("build_mock_criteria", wrap(build_mock_criteria))
    builder.add_edge(START, "load_mock_business_context")
    builder.add_edge("load_mock_business_context", "build_mock_criteria")
    builder.add_edge("build_mock_criteria", END)
    return builder.compile()
