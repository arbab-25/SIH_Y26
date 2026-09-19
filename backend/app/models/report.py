"""Report model — formal compliance reports with PDF and sharing."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUID_TYPE


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("scans.id"), nullable=False, index=True
    )
    report_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    pdf_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE, ForeignKey("users.id"), nullable=True
    )
    emailed_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    share_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    scan = relationship("Scan", back_populates="reports")
    generated_by_user = relationship("User", back_populates="reports")
    email_logs = relationship(
        "EmailLog", back_populates="report", cascade="all, delete-orphan"
    )
