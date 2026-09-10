from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from time import monotonic

from app.evidence.models import Evidence, VerificationBudget, VerifiedEnterpriseProfile

TargetedProvider = Callable[[str, list[str]], list[Evidence] | Awaitable[list[Evidence]]]


class VerificationBudgetGuard:
    def __init__(self, budget: VerificationBudget) -> None:
        self.budget = budget
        self.used_calls = 0
        self.used_pages = 0
        self.rounds = 0
        self.entity_calls: dict[str, int] = defaultdict(int)
        self.started_at = monotonic()

    def reserve(self, enterprise_id: str, *, calls: int = 1, pages: int = 0) -> bool:
        if monotonic() - self.started_at >= self.budget.max_runtime_seconds:
            return False
        if self.used_calls + calls > self.budget.max_extra_tool_calls:
            return False
        if self.used_pages + pages > self.budget.max_web_pages:
            return False
        if self.entity_calls[enterprise_id] + calls > self.budget.max_calls_per_entity:
            return False
        self.used_calls += calls
        self.used_pages += pages
        self.entity_calls[enterprise_id] += calls
        return True

    def start_round(self) -> bool:
        if self.rounds >= self.budget.max_rounds:
            return False
        self.rounds += 1
        return True


class TargetedVerificationService:
    def __init__(self, repository, provider: TargetedProvider, guard: VerificationBudgetGuard) -> None:
        self.repository = repository
        self.provider = provider
        self.guard = guard

    async def enrich(self, profile: VerifiedEnterpriseProfile, fields: list[str]) -> list[Evidence]:
        requested = [name for name in fields if name in profile.required_fields]
        estimated_calls = min(len(requested), self.guard.budget.max_calls_per_entity)
        estimated_pages = 1 if set(requested) & {"website", "public_phone"} else 0
        if not requested or not self.guard.reserve(
            profile.enterprise_id, calls=estimated_calls, pages=estimated_pages
        ):
            return []
        result = self.provider(profile.enterprise_id, requested)
        values = await result if inspect.isawaitable(result) else result
        return [self.repository.save_evidence(item) for item in values]
