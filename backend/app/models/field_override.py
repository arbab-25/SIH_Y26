"""FieldOverride model — inspector corrections to OCR-extracted fields."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUID_TYPE


class FieldOverride(Base):
    __tablename__ = "field_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    overridden_by: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    scan = relationship("Scan", back_populates="field_overrides")
    overridden_by_user = relationship("User", back_populates="overrides")
