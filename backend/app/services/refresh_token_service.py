"""Refresh-token service — rotation, revocation, and theft detection.

Flow (industry standard):
1. Login returns {access_token (short JWT), refresh_token (opaque, long)}.
2. POST /auth/refresh exchanges a valid refresh token for a NEW pair; the old
   token is marked revoked and linked to its replacement (rotation).
3. Presenting an ALREADY-ROTATED token is treated as theft: the whole token
   family is revoked and the caller gets 401.
4. POST /auth/logout revokes the presented token; DELETE /auth/sessions
   (admin) or logout-all revokes every token a user owns.

Tokens are stored only as SHA-256 hashes (Rule 5: no secrets at rest).
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_token import RefreshToken


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ttl_days() -> int:
    return max(1, int(getattr(settings, "REFRESH_TOKEN_TTL_DAYS", 30)))


def issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    family_id: Optional[uuid.UUID] = None,
    user_agent: Optional[str] = None,
) -> str:
    """Create (and persist) a new refresh token; returns the raw token once."""
    raw = secrets.token_urlsafe(48)
    token = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        family_id=family_id or uuid.uuid4(),
        expires_at=datetime.utcnow() + timedelta(days=_ttl_days()),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(token)
    return raw


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str, user_agent: Optional[str] = None
) -> Optional[tuple]:
    """Validate + rotate a refresh token. Returns (user_id, new_raw_token, family_id).

    - Unknown/expired/revoked token -> None (401 for the caller).
    - Token already rotated once -> theft: revoke its whole family, return None.
    """
    token_hash = _hash_token(raw_token)
    res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token = res.scalar_one_or_none()
    if token is None:
        return None

    if token.family_revoked or (token.revoked_at is not None):
        # Reuse of a rotated/revoked token = theft signal for this family.
        if token.family_revoked:
            return None
        await revoke_family(db, token.family_id)
        return None

    if token.expires_at <= datetime.utcnow():
        return None

    # Rotate: revoke current, issue a child in the same family.
    replacement_id = uuid.uuid4()
    token.revoked_at = datetime.utcnow()
    token.replaced_by_id = replacement_id

    new_raw = secrets.token_urlsafe(48)
    new_token = RefreshToken(
        id=replacement_id,
        user_id=token.user_id,
        token_hash=_hash_token(new_raw),
        family_id=token.family_id,
        expires_at=datetime.utcnow() + timedelta(days=_ttl_days()),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(new_token)
    return token.user_id, new_raw, token.family_id


async def revoke_token(db: AsyncSession, raw_token: str) -> bool:
    """Logout: revoke the presented token. True when a live token was revoked."""
    token_hash = _hash_token(raw_token)
    res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token = res.scalar_one_or_none()
    if token is None or token.revoked_at is not None or token.family_revoked:
        return False
    token.revoked_at = datetime.utcnow()
    return True


async def revoke_family(db: AsyncSession, family_id: uuid.UUID) -> int:
    """Kill every token in a family (theft response / device logout)."""
    res = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow(), family_revoked=True)
    )
    return res.rowcount or 0


async def revoke_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Logout-everywhere: revoke every live token the user owns."""
    res = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )
    return res.rowcount or 0
