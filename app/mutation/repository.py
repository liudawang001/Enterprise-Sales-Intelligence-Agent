from __future__ import annotations

from copy import deepcopy

from app.mutation.models import ReexecutionPlan, TaskMutation


class InMemoryMutationRepository:
    def __init__(self) -> None:
        self.mutations: dict[str, TaskMutation] = {}
        self.plans: dict[str, ReexecutionPlan] = {}
        self._by_request: dict[tuple[str, str], str] = {}

    def save_mutation(self, value: TaskMutation) -> TaskMutation:
        key = (value.task_id, value.source_message_id)
        existing_id = self._by_request.get(key)
        if existing_id:
            return deepcopy(self.mutations[existing_id])
        self.mutations[value.mutation_id] = deepcopy(value)
        self._by_request[key] = value.mutation_id
        return deepcopy(value)

    def update_mutation(self, value: TaskMutation) -> TaskMutation:
        self.mutations[value.mutation_id] = deepcopy(value)
        self._by_request[(value.task_id, value.source_message_id)] = value.mutation_id
        return deepcopy(value)

    def get_mutation(self, mutation_id: str) -> TaskMutation | None:
        value = self.mutations.get(mutation_id)
        return deepcopy(value) if value else None

    def find_mutation(self, task_id: str, source_message_id: str) -> TaskMutation | None:
        return self.get_mutation(self._by_request.get((task_id, source_message_id), ""))

    def save_plan(self, value: ReexecutionPlan) -> ReexecutionPlan:
        self.plans[value.plan_id] = deepcopy(value)
        return deepcopy(value)

    def get_plan(self, plan_id: str) -> ReexecutionPlan | None:
        value = self.plans.get(plan_id)
        return deepcopy(value) if value else None
