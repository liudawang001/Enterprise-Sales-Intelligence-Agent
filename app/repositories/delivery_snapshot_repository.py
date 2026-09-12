from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.delivery.models import DeliveryBundle, DeliverySnapshot
from app.persistence.models.delivery import DeliverySnapshotRecord


class InMemoryDeliverySnapshotRepository:
    def __init__(self) -> None:
        self.bundles: dict[str, DeliveryBundle] = {}
        self._by_execution: dict[tuple[str, int, str | None], str] = {}

    def save(self, value: DeliveryBundle) -> DeliveryBundle:
        snapshot = value.snapshot
        self.bundles[snapshot.snapshot_id] = deepcopy(value)
        self._by_execution[
            (snapshot.task_id, snapshot.task_version, snapshot.execution_snapshot_id)
        ] = snapshot.snapshot_id
        return deepcopy(value)

    def get(self, snapshot_id: str | None) -> DeliveryBundle | None:
        value = self.bundles.get(snapshot_id or "")
        return deepcopy(value) if value else None

    def for_execution(
        self, task_id: str, task_version: int, execution_snapshot_id: str | None
    ) -> DeliveryBundle | None:
        return self.get(
            self._by_execution.get((task_id, task_version, execution_snapshot_id))
        )


class DeliverySnapshotRepository:
    """PostgreSQL metadata adapter; immutable DTO payloads remain in source tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, value: DeliverySnapshot) -> DeliverySnapshot:
        if not await self.session.get(DeliverySnapshotRecord, UUID(value.snapshot_id)):
            self.session.add(
                DeliverySnapshotRecord(
                    id=UUID(value.snapshot_id),
                    task_id=value.task_id,
                    task_version=value.task_version,
                    criteria_snapshot_id=UUID(value.criteria_snapshot_id)
                    if value.criteria_snapshot_id
                    else None,
                    verified_lead_set_id=UUID(value.verified_lead_set_id),
                    lead_score_set_id=UUID(value.lead_score_set_id),
                    scoring_profile_id=UUID(value.scoring_profile_id)
                    if value.scoring_profile_id
                    else None,
                    execution_snapshot_id=UUID(value.execution_snapshot_id)
                    if value.execution_snapshot_id
                    else None,
                    result_count=value.result_count,
                    created_at=value.created_at,
                )
            )
            await self.session.flush()
        return value
