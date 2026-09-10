import re
from typing import Any

from app.agent.enums import MutationScope
from app.domain.task import LeadTask, TaskPatch
from app.repositories.mock_task_repository import MockTaskRepository


class TaskService:
    def __init__(self, repository: MockTaskRepository) -> None:
        self.repository = repository

    def create_or_get_task(self, session_id: str) -> LeadTask:
        return self.repository.create_task(session_id)

    def apply_patch(self, task_id: str, patch: TaskPatch) -> LeadTask:
        return self.repository.apply_patch(task_id, patch)

    def classify_mutation(self, text: str, task: LeadTask | None) -> tuple[MutationScope, str]:
        if task is None:
            return MutationScope.FULL_REPLAN, "No active task is available"
        normalized = text.strip()
        if re.search(r"企业专线|改成.*业务|业务改|换成", normalized):
            return MutationScope.FULL_REPLAN, "Business changed"
        count_match = re.search(r"(?:数量|改成|改为|目标).*?(\d+)\s*家?", normalized)
        if count_match:
            new_count = int(count_match.group(1))
            if task.target_count is not None and new_count <= task.target_count:
                return MutationScope.DISPLAY_ONLY, "Target count reduced"
            return MutationScope.RANK_ONLY, "Target count increased within verified set"
        if "排序" in normalized or "权重" in normalized:
            return MutationScope.RANK_ONLY, "Ranking preference changed"
        return MutationScope.FULL_REPLAN, "Mutation requires a new plan"

    def parse_mutation(self, text: str) -> TaskPatch:
        match = re.search(r"(?:数量|改成|改为|目标).*?(\d+)\s*家?", text)
        if match:
            return TaskPatch(target_count=int(match.group(1)))
        if "企业专线" in text:
            return TaskPatch(business="企业专线")
        return TaskPatch()
