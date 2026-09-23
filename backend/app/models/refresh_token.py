"""RefreshToken model — rotating refresh tokens with revocation.

Short-lived access JWTs (unchanged) + long-lived refresh tokens stored
hashed. Revocation is per-token AND per-user (logout everywhere). Family
tracking detects token theft: reusing a rotated token kills the whole family.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.types import UUID_TYPE


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE, ForeignKey("users.id"), nullable=False, index=True
    )
    # SHA-256 of the token string — the raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Set when reuse of a rotated token was detected: every token in the family
    # is revoked at once (theft response).
    family_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        return (
            self.revoked_at is None
            and not self.family_revoked
            and self.expires_at > datetime.utcnow()
        )
