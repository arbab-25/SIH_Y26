"""Scan model — each label analysis attempt."""

import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUID_TYPE, JSON_TYPE
import enum


class ScanStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Verdict(str, enum.Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE, ForeignKey("users.id"), nullable=True, index=True
    )
    guest_device_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    image_urls: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    package_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ScanStatus] = mapped_column(
        SAEnum(ScanStatus, name="scan_status", create_constraint=True),
        default=ScanStatus.QUEUED,
        nullable=False,
    )
    verdict: Mapped[Verdict | None] = mapped_column(
        SAEnum(Verdict, name="verdict_type", create_constraint=True),
        nullable=True,
    )
    compliance_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    avg_ocr_confidence: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_engine: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geo_lat: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    geo_lng: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    user = relationship("User", back_populates="scans")
    product = relationship("Product", back_populates="scan", uselist=False)
    extracted_fields = relationship(
        "ExtractedField", back_populates="scan", cascade="all, delete-orphan"
    )
    violations = relationship(
        "Violation", back_populates="scan", cascade="all, delete-orphan"
    )
    field_overrides = relationship(
        "FieldOverride", back_populates="scan", cascade="all, delete-orphan"
    )
    reports = relationship("Report", back_populates="scan")
