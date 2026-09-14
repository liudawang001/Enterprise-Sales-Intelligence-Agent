import re

from pydantic import BaseModel, Field

from app.agent.enums import IntentType
from app.agent.state import AgentState


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0, le=1)
    reason: str = ""


def classify_intent(state: AgentState, llm=None) -> dict:
    text = (state.get("incoming_text") or "").strip()
    active_task = state.get("active_task_id")
    if re.search(r"导出.*Excel|Excel.*导出|导出", text, re.IGNORECASE):
        intent = IntentType.EXPORT_REQUEST
    elif re.search(r"(?:新建|新增|另建|再建|帮我找|寻找).*(?:集团V网|企业专线)", text):
        intent = IntentType.LEAD_DISCOVERY
    elif active_task and re.search(r"数量|改成|改为|改到|换成|还是|不限制|不要限制|排序|权重|优先|最好|必须|排除|成员数|员工数|员工|办公点|再补|加上|增加", text):
        intent = IntentType.TASK_MODIFICATION
    elif re.search(r"为什么.*(?:评分|条件|要求)|评分.*最高|第\d+家|Criteria|条件.*版本", text, re.IGNORECASE):
        intent = IntentType.LEAD_QUERY
    elif re.search(r"是什么|怎么|含义|介绍|什么客户|哪些企业|适合什么", text) and ("集团V网" in text or "企业专线" in text):
        intent = IntentType.BUSINESS_QA
    elif re.search(r"找|筛选|潜客|客户|企业", text) and ("集团V网" in text or "企业专线" in text):
        intent = IntentType.LEAD_DISCOVERY
    else:
        intent = IntentType.GENERAL_CHAT
    result = {"intent": intent.value, "intent_confidence": 1.0}
    # Rule-based routing remains the fast path. Only ambiguous text uses the
    # injected real model, and any provider/parse failure safely falls back.
    if llm is not None and getattr(llm, "provider", "fake") != "fake" and intent == IntentType.GENERAL_CHAT:
        try:
            prompt = (
                "Return valid json only. Classify the user message into exactly one intent "
                "from BUSINESS_QA, LEAD_DISCOVERY, TASK_MODIFICATION, LEAD_QUERY, EXPORT_REQUEST, GENERAL_CHAT. "
                "Do not invent a task or facts.\n"
                f"User message: {text}"
            )
            if hasattr(llm, "structured"):
                parsed = llm.structured(IntentResult, prompt, metadata={"operation": "classify_intent"})
            else:
                parsed = llm.with_structured_output(IntentResult, method="json_mode").invoke(prompt)
            result = {"intent": parsed.intent.value, "intent_confidence": parsed.confidence}
        except Exception:
            pass
    return result
