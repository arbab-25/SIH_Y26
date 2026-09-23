"""Authentication service — JWT tokens + bcrypt password hashing."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserRole


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, role: str) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def register_user(
    db: AsyncSession,
    name: str,
    password: str,
    email: Optional[str] = None,
    mobile: Optional[str] = None,
    role: str = "INSPECTOR",
    designation: Optional[str] = None,
    office: Optional[str] = None,
    district: Optional[str] = None,
    state: Optional[str] = None,
) -> User:
    """Register a new user. Raises ValueError if email/mobile already exists."""
    # Check for existing user
    conditions = []
    if email:
        conditions.append(User.email == email)
    if mobile:
        conditions.append(User.mobile == mobile)

    if conditions:
        result = await db.execute(select(User).where(or_(*conditions)))
        existing = result.scalar_one_or_none()
        if existing:
            if existing.email == email:
                raise ValueError("Email already registered")
            if existing.mobile == mobile:
                raise ValueError("Mobile number already registered")

    user = User(
        id=uuid.uuid4(),
        name=name,
        email=email,
        mobile=mobile,
        password_hash=hash_password(password),
        role=UserRole(role),
        designation=designation,
        office=office,
        district=district,
        state=state,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(
    db: AsyncSession, identifier: str, password: str
) -> User | None:
    """Authenticate by email or mobile. Returns User or None."""
    # Determine if identifier is email or mobile
    if "@" in identifier:
        stmt = select(User).where(User.email == identifier, User.is_active.is_(True))
    else:
        stmt = select(User).where(User.mobile == identifier, User.is_active.is_(True))

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user and verify_password(password, user.password_hash):
        # Update last_login
        user.last_login = datetime.utcnow()
        await db.flush()
        return user
    return None


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a user by UUID."""
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    return result.scalar_one_or_none()
