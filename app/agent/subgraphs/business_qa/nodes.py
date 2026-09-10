from app.agent.state import AgentState


def mock_retrieve(state: AgentState) -> dict:
    return {"business_context_refs": ["mock-business-knowledge"]}


def mock_answer(state: AgentState) -> dict:
    return {
        "response_text": (
            "集团V网是面向集团客户内部通信场景的业务。\n\n"
            "当前为 Phase 1 Mock Answer，尚未接入真实RAG知识库。"
        )
    }
