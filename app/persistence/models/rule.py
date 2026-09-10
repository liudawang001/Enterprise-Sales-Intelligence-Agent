from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class BusinessCatalogRecord(Base):
    __tablename__ = "business_catalog"
    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[list] = mapped_column(JSONB, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class BusinessRuleRecord(Base):
    __tablename__ = "business_rules"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    business_code: Mapped[str] = mapped_column(String(80), index=True)
    field: Mapped[str] = mapped_column(String(120))
    operator: Mapped[str] = mapped_column(String(20))
    value: Mapped[object] = mapped_column(JSONB)
    value_type: Mapped[str] = mapped_column(String(30))
    source_type: Mapped[str] = mapped_column(String(40))
    constraint_type: Mapped[str] = mapped_column(String(20))
    modality: Mapped[str | None] = mapped_column(String(30))
    weight: Mapped[float | None] = mapped_column(Numeric)
    confidence: Mapped[float] = mapped_column(Numeric)
    rationale: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(80))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    source_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BusinessRuleEvidenceRecord(Base):
    __tablename__ = "business_rule_evidence"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    rule_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("business_rules.id", ondelete="CASCADE"))
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    chunk_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    excerpt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MarketingRuleRecord(Base):
    __tablename__ = "business_marketing_rules"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    business_code: Mapped[str] = mapped_column(String(80), index=True)
    field: Mapped[str] = mapped_column(String(120))
    operator: Mapped[str] = mapped_column(String(20))
    value: Mapped[object] = mapped_column(JSONB)
    value_type: Mapped[str] = mapped_column(String(30))
    constraint_type: Mapped[str] = mapped_column(String(20))
    weight: Mapped[float | None] = mapped_column(Numeric)
    region: Mapped[str | None] = mapped_column(String(80))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    source_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LeadCriteriaSnapshotRecord(Base):
    __tablename__ = "lead_criteria_snapshots"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    task_version: Mapped[int] = mapped_column(Integer)
    business_code: Mapped[str] = mapped_column(String(80))
    region_scope: Mapped[list] = mapped_column(JSONB)
    target_count: Mapped[int] = mapped_column(Integer)
    hard_constraints: Mapped[list] = mapped_column(JSONB)
    soft_constraints: Mapped[list] = mapped_column(JSONB)
    required_fields: Mapped[list] = mapped_column(JSONB)
    ranking_preferences: Mapped[list] = mapped_column(JSONB)
    source_rule_ids: Mapped[list] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)
    criteria_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

