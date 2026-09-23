"""SchedulePackSize model — standard pack quantities from Second Schedule."""

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import JSON_TYPE, UUID_TYPE


class SchedulePackSize(Base):
    __tablename__ = "schedule_pack_sizes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    commodity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    allowed_values: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    rule_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
