from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from app.exports.hashing import export_request_hash
from app.exports.models import CreateExportRequest, ExportJob, ExportSpec, ExportStatus
from app.exports.registry import ExportFieldRegistry
from app.exports.sanitizer import sanitize_filename
from app.exports.workbook import build_workbook


class ExportError(ValueError):
    pass


class ExportService:
    NULLABLE_FACT_FIELDS: ClassVar[set[str]] = {
        "parent_enterprise",
        "industry",
        "company_scale",
        "region",
        "office_count",
        "office_address",
        "public_phone",
        "website",
        "lead_score",
        "evidence_confidence",
        "recommendation_reason",
        "primary_source",
        "primary_source_url",
        "verified_at",
    }

    def __init__(self, delivery, repository, storage, registry=None) -> None:
        self.delivery = delivery
        self.repository = repository
        self.storage = storage
        self.registry = registry or ExportFieldRegistry()

    def create_export(self, request: CreateExportRequest) -> ExportJob:
        try:
            bundle = (
                self.delivery.get_bundle(request.snapshot_id)
                if request.snapshot_id
                else self.delivery.freeze(request.task_id, request.task_version)
            )
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        if bundle.snapshot.task_id != request.task_id:
            raise ExportError("EXPORT_SNAPSHOT_TASK_MISMATCH")
        if request.task_version is not None and bundle.snapshot.task_version != request.task_version:
            raise ExportError("EXPORT_SNAPSHOT_VERSION_MISMATCH")
        try:
            fields = self.registry.validate(request.fields)
        except ValueError as exc:
            raise ExportError(str(exc)) from exc
        count = request.target_count or len(bundle.leads)
        if count > len(bundle.leads):
            raise ExportError("EXPORT_TARGET_COUNT_EXCEEDS_SNAPSHOT")
        self._validate_completeness(bundle.leads[:count], request.fields)
        filename = sanitize_filename(
            request.filename or self._default_filename(bundle.task, count)
        )
        spec = ExportSpec(
            task_id=bundle.snapshot.task_id,
            task_version=bundle.snapshot.task_version,
            source_lead_set_id=bundle.snapshot.verified_lead_set_id,
            source_score_set_id=bundle.snapshot.lead_score_set_id,
            target_count=count,
            fields=request.fields,
            include_task_summary=request.include_task_summary,
            include_score_breakdown=request.include_score_breakdown,
            include_evidence_summary=request.include_evidence_summary,
            include_conflicts=request.include_conflicts,
            filename=filename,
        )
        request_hash = export_request_hash(
            {
                "snapshot_id": bundle.snapshot.snapshot_id,
                **spec.model_dump(mode="json"),
            }
        )
        existing = self.repository.successful_for_hash(request_hash)
        if existing:
            return existing
        job = self.repository.save(
            ExportJob(
                snapshot_id=bundle.snapshot.snapshot_id,
                task_id=spec.task_id,
                task_version=spec.task_version,
                requested_fields=list(spec.fields),
                request_hash=request_hash,
                file_name=filename,
            )
        )
        self.repository.record_event(job.export_id, "EXPORT_STARTED", status="GENERATING")
        job = self.repository.save(job.model_copy(update={"status": ExportStatus.GENERATING}))
        try:
            created_at = datetime.now(UTC)
            content = build_workbook(
                bundle,
                fields,
                target_count=count,
                export_id=job.export_id,
                exported_at=created_at,
                include_task_summary=spec.include_task_summary,
                include_score_breakdown=spec.include_score_breakdown,
                include_evidence_summary=spec.include_evidence_summary,
                include_conflicts=spec.include_conflicts,
            )
            stored = self.storage.save(job.export_id, filename, content)
            job = job.model_copy(
                update={
                    "status": ExportStatus.COMPLETED,
                    "row_count": count,
                    "artifact_path": stored.artifact_path,
                    "file_name": stored.file_name,
                    "file_size": stored.file_size,
                    "sha256": stored.sha256,
                    "completed_at": datetime.now(UTC),
                }
            )
            self.repository.record_event(job.export_id, "EXPORT_COMPLETED", status="COMPLETED")
            return self.repository.save(job)
        except Exception as exc:
            failed = job.model_copy(
                update={
                    "status": ExportStatus.FAILED,
                    "error_code": "EXPORT_GENERATION_FAILED",
                    "error_message": str(exc),
                    "completed_at": datetime.now(UTC),
                }
            )
            self.repository.record_event(failed.export_id, "EXPORT_FAILED", status="FAILED")
            self.repository.save(failed)
            raise ExportError("EXPORT_GENERATION_FAILED") from exc

    def _validate_completeness(self, leads: list[object], fields: list[str]) -> None:
        missing = {
            field: sum(getattr(lead, field) is None for lead in leads)
            for field in fields
            if field in self.NULLABLE_FACT_FIELDS
        }
        missing = {field: count for field, count in missing.items() if count}
        if missing:
            detail = ",".join(f"{field}={count}" for field, count in sorted(missing.items()))
            raise ExportError(f"EXPORT_FIELD_DATA_INCOMPLETE:{detail}")

    @staticmethod
    def _default_filename(task: object, count: int) -> str:
        date = datetime.now(UTC).strftime("%Y%m%d")
        return (
            f"{task.business or '潜客'}_{task.region or '全部区域'}_"
            f"TaskV{task.viewed_version}_Top{count}_{date}.xlsx"
        )
