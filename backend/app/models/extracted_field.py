"""ExtractedField model — individual OCR-extracted fields with confidence."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.scan import Verdict
from app.models.types import JSON_TYPE, UUID_TYPE


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    source_image_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[Verdict] = mapped_column(
        SAEnum(Verdict, name="verdict_type", create_constraint=False,
               create_type=False),
        default=Verdict.NEEDS_REVIEW,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    scan = relationship("Scan", back_populates="extracted_fields")
