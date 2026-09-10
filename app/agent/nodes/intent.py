import re

from app.agent.enums import IntentType
from app.agent.state import AgentState


def classify_intent(state: AgentState) -> dict:
    text = (state.get("incoming_text") or "").strip()
    active_task = state.get("active_task_id")
    if re.search(r"导出.*Excel|Excel.*导出|导出", text, re.IGNORECASE):
        intent = IntentType.EXPORT_REQUEST
    elif active_task and re.search(r"数量|改成|改为|企业专线|不限制|排序|权重", text):
        intent = IntentType.TASK_MODIFICATION
    elif re.search(r"为什么.*评分|评分.*最高|第\d+家", text):
        intent = IntentType.LEAD_QUERY
    elif re.search(r"是什么|怎么|含义|介绍", text) and "集团V网" in text:
        intent = IntentType.BUSINESS_QA
    elif re.search(r"找|筛选|潜客|客户|企业", text) and ("集团V网" in text or "企业专线" in text):
        intent = IntentType.LEAD_DISCOVERY
    else:
        intent = IntentType.GENERAL_CHAT
    return {"intent": intent.value, "intent_confidence": 1.0}
