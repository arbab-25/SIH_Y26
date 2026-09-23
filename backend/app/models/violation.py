"""Violation model — rule violations found during scan analysis."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import UUID_TYPE


class Severity(str, enum.Enum):
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE, ForeignKey("rules.id"), nullable=True, index=True
    )
    # Exact rule reference (e.g. 'rule-6-1-e') persisted with the violation so
    # the UI can deep-link into the Rule Book — synthetic field-name refs made
    # every deep link land on a 404.
    rule_ref: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="severity_type", create_constraint=True),
        default=Severity.MAJOR,
        nullable=False,
    )
    message_en: Mapped[str] = mapped_column(Text, nullable=False)
    message_hi: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    scan = relationship("Scan", back_populates="violations")
    rule = relationship("Rule", back_populates="violations")
