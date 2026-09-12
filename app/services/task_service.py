import re

from app.agent.enums import MutationScope
from app.domain.task import LeadTask, TaskPatch
from app.repositories.mock_task_repository import MockTaskRepository


class TaskService:
    def __init__(self, repository: MockTaskRepository) -> None:
        self.repository = repository

    def create_or_get_task(self, session_id: str, source_message_id: str | None = None) -> LeadTask:
        return self.repository.create_task(session_id, source_message_id)

    def apply_patch(self, task_id: str, patch: TaskPatch) -> LeadTask:
        return self.repository.apply_patch(task_id, patch)

    def classify_mutation(self, text: str, task: LeadTask | None) -> tuple[MutationScope, str]:
        if task is None:
            return MutationScope.FULL_REPLAN, "No active task is available"
        normalized = text.strip()
        if re.search(r"企业专线|改成.*业务|业务改|换成", normalized):
            return MutationScope.FULL_REPLAN, "Business changed"
        if re.search(r"不限制.*行业|不要限制.*行业|制造业优先|物流优先|优先", normalized):
            return MutationScope.RANK_ONLY, "Soft criteria changed"
        if re.search(r"松江|浦东|必须|只要|排除|员工|成员|办公点", normalized):
            return MutationScope.FILTER_ONLY, "Hard criteria changed"
        count_match = re.search(r"(?:数量|改成|改为|目标|还是).*?(\d+)\s*家?", normalized)
        if count_match:
            new_count = int(count_match.group(1))
            if task.target_count is not None and new_count <= task.target_count:
                return MutationScope.DISPLAY_ONLY, "Target count reduced"
            return MutationScope.RANK_ONLY, "Target count increased within verified set"
        if "排序" in normalized or "权重" in normalized:
            return MutationScope.RANK_ONLY, "Ranking preference changed"
        return MutationScope.FULL_REPLAN, "Mutation requires a new plan"

    def parse_mutation(self, text: str) -> TaskPatch:
        match = re.search(r"(?:数量|改成|改为|目标|还是).*?(\d+)\s*家?", text)
        if match:
            return TaskPatch(target_count=int(match.group(1)))
        if re.search(r"(?:改成|换成|改为)企业专线", text):
            return TaskPatch(business="企业专线")
        if "集团V网" in text and re.search(r"改成|换成|改为", text):
            return TaskPatch(business="集团V网")
        region = re.search(r"(?:改到|改为|必须在|换到)(上海)?(松江|浦东)", text)
        if region:
            return TaskPatch(region=f"上海{region.group(2)}")
        if re.search(r"(?:不|不要|不再)限制(?:制造业|行业)", text):
            return TaskPatch(constraints=[{"field": "industry", "operation": "REMOVE"}])
        if re.search(r"不(?:再)?限制.*员工|不要.*员工.*限制|取消.*员工", text):
            return TaskPatch(constraints=[{"field": "employee_count", "operation": "REMOVE"}])
        employee = re.search(r"员工(?:数|数量)?\s*(\d+)\s*人?(?:以上|起)", text)
        if employee:
            return TaskPatch(constraints=[{"field": "employee_count", "operation": "ADD", "operator": "GTE", "value": int(employee.group(1)), "constraint_type": "HARD"}])
        if re.search(r"(?:再补|增加|加上|需要).*(?:官网|网站)", text):
            return TaskPatch(required_fields=["company_name", "phone", "address", "website"])
        preferred = re.search(r"(?:最好|优先)?\s*(制造业|物流|科技|零售|金融)(?:行业|企业)?\s*(?:优先|最好|更好)?", text)
        if preferred:
            return TaskPatch(constraints=[{"field": "industry", "operation": "ADD", "operator": "EQ", "value": preferred.group(1), "constraint_type": "SOFT"}])
        member = re.search(r"成员(?:数|数量).*?(至少|不少于|少于|小于)\s*(\d+)", text)
        if member:
            operator = "GTE" if member.group(1) in {"至少", "不少于"} else "LT"
            return TaskPatch(constraints=[{"field": "member_count", "operation": "ADD", "operator": operator, "value": int(member.group(2)), "constraint_type": "HARD"}])
        if re.search(r"多个办公点.*(?:更重要|权重|优先)|(?:提高|增加).*办公点.*权重", text):
            return TaskPatch(constraints=[{"field": "office_count", "operation": "UPDATE", "operator": "GTE", "value": 2, "constraint_type": "SOFT"}])
        return TaskPatch()
