from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exports.models import ExportJob, ExportStatus
from app.persistence.models.delivery import ExportRecord


class InMemoryExportRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, ExportJob] = {}
        self._successful_by_hash: dict[str, str] = {}
        self.events: dict[str, list[dict]] = {}

    def save(self, value: ExportJob) -> ExportJob:
        self.jobs[value.export_id] = deepcopy(value)
        if value.status == ExportStatus.COMPLETED:
            self._successful_by_hash[value.request_hash] = value.export_id
        return deepcopy(value)

    def get(self, export_id: str | None) -> ExportJob | None:
        value = self.jobs.get(export_id or "")
        return deepcopy(value) if value else None

    def successful_for_hash(self, request_hash: str) -> ExportJob | None:
        return self.get(self._successful_by_hash.get(request_hash))

    def list_for_task(self, task_id: str) -> list[ExportJob]:
        values = [item for item in self.jobs.values() if item.task_id == task_id]
        return [deepcopy(item) for item in sorted(values, key=lambda item: item.created_at, reverse=True)]

    def record_event(self, export_id: str, event: str, **data: object) -> None:
        self.events.setdefault(export_id, []).append({"event": event, **data})


class ExportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, value: ExportJob) -> ExportJob:
        record = await self.session.get(ExportRecord, UUID(value.export_id))
        fields = {
            "snapshot_id": UUID(value.snapshot_id),
            "task_id": value.task_id,
            "task_version": value.task_version,
            "format": value.format,
            "fields_json": value.requested_fields,
            "status": value.status.value,
            "row_count": value.row_count,
            "artifact_path": value.artifact_path,
            "file_name": value.file_name,
            "file_size": value.file_size,
            "sha256": value.sha256,
            "request_hash": value.request_hash,
            "created_at": value.created_at,
            "completed_at": value.completed_at,
            "error_code": value.error_code,
            "error_message": value.error_message,
        }
        if record:
            for key, item in fields.items():
                setattr(record, key, item)
        else:
            self.session.add(ExportRecord(id=UUID(value.export_id), **fields))
        await self.session.flush()
        return value

    async def successful_for_hash(self, request_hash: str) -> ExportJob | None:
        record = await self.session.scalar(
            select(ExportRecord).where(
                ExportRecord.request_hash == request_hash,
                ExportRecord.status == ExportStatus.COMPLETED.value,
            )
        )
        if not record:
            return None
        return ExportJob(
            export_id=str(record.id),
            snapshot_id=str(record.snapshot_id),
            task_id=record.task_id,
            task_version=record.task_version,
            status=record.status,
            format=record.format,
            requested_fields=record.fields_json,
            row_count=record.row_count,
            artifact_path=record.artifact_path,
            file_name=record.file_name,
            file_size=record.file_size,
            sha256=record.sha256,
            request_hash=record.request_hash,
            created_at=record.created_at,
            completed_at=record.completed_at,
            error_code=record.error_code,
            error_message=record.error_message,
        )
