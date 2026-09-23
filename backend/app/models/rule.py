"""Rule model — legal rules parsed from RULE_BOOK.pdf."""

import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import JSON_TYPE, TSVECTOR_TYPE, UUID_TYPE


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4
    )
    rule_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    chapter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    applies_to: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR_TYPE, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    violations = relationship("Violation", back_populates="rule", lazy="dynamic")
