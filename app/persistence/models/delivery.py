from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class DeliverySnapshotRecord(Base):
    __tablename__ = "delivery_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    task_version: Mapped[int] = mapped_column(Integer, nullable=False)
    criteria_snapshot_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    verified_lead_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    lead_score_set_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    scoring_profile_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    execution_snapshot_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bundle_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExportRecord(Base):
    __tablename__ = "exports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("delivery_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(120), nullable=False, default="local", index=True)
    task_version: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    fields_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    events_json: Mapped[list] = mapped_column(JSONB, default=list)
