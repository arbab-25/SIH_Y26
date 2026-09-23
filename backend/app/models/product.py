"""Product model — extracted product data from a scan."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import UUID_TYPE


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generic_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manufacturer_name: Mapped[str | None] = mapped_column(
        String(500), nullable=True, index=True
    )
    manufacturer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    net_quantity_value: Mapped[float | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    net_quantity_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mrp: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    mrp_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfg_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mfg_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_before: Mapped[str | None] = mapped_column(String(100), nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fssai_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consumer_care_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consumer_care_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    barcode_gtin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    scan = relationship("Scan", back_populates="product")
