"""RuleVersion model — rules are versioned data, not code.

Every scan result records the rule version it was evaluated against, so an
amendment to the Legal Metrology rules never silently rewrites history: old
scans keep pointing at the version that decided them. Amendments ship as a
new version row + seed JSON update; no code changes needed.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.types import UUID_TYPE


class RuleVersion(Base):
    __tablename__ = "rule_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    # e.g. "LMPC-2011-GSR629E-2018" — human-readable, env-independent
    version_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Set by the seed script from the versioned seed JSON
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
