from langgraph.graph import END, START, StateGraph

from app.agent.dependencies import AgentDependencies
from app.agent.state import AgentState
from app.agent.subgraphs.mutation.nodes import load_current_task, parse_mutation


def build_mutation_graph(deps: AgentDependencies):
    builder = StateGraph(AgentState)

    def wrap(fn):
        def node(state):
            return fn({**state, "_deps": deps})
        return node

    builder.add_node("load_current_task", wrap(load_current_task))
    builder.add_node("parse_mutation", wrap(parse_mutation))
    builder.add_edge(START, "load_current_task")
    builder.add_edge("load_current_task", "parse_mutation")
    builder.add_edge("parse_mutation", END)
    return builder.compile()
