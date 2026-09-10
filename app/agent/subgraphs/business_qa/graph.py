from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.agent.subgraphs.business_qa.nodes import mock_answer, mock_retrieve


def build_business_qa_graph():
    builder = StateGraph(AgentState)
    builder.add_node("mock_retrieve", mock_retrieve)
    builder.add_node("mock_answer", mock_answer)
    builder.add_edge(START, "mock_retrieve")
    builder.add_edge("mock_retrieve", "mock_answer")
    builder.add_edge("mock_answer", END)
    return builder.compile()
