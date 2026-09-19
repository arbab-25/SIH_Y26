"""Authentication API Router — Register, Login (email or mobile), Me profile.

Hardening per security checklist:
- Rate limiting on login and register (brute-force / enumeration defense)
- Strict input sanitization (strip control chars, length caps) before DB writes
- Uniform 'invalid credentials' message (no user enumeration)
"""

import re
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas import RegisterRequest, LoginRequest, AuthResponse, UserResponse, TokenResponse
from app.services.auth_service import (
    authenticate_user,
    register_user,
    create_access_token,
)
from app.api.deps import get_current_user
from app.utils.rate_limit import check_rate_limit

router = APIRouter(prefix="/auth", tags=["Auth"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _sanitize(value, max_len: int = 255):
    """Strip control characters and trim; returns None for empty input."""
    if value is None:
        return None
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", str(value)).strip()
    return cleaned[:max_len] if cleaned else None


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Login using either email OR 10-digit mobile number + password."""
    # Rate limit by IP+identifier to slow credential stuffing (10 attempts / 5 min)
    check_rate_limit(
        f"login:{_client_ip(request)}:{req.identifier[:64]}",
        max_requests=10,
        window_seconds=300,
    )

    identifier = _sanitize(req.identifier, 255)
    password = req.password
    if not identifier or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifier and password are required")

    user = await authenticate_user(db, identifier, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/mobile or password"
        )

    token = create_access_token(str(user.id), user.role.value if hasattr(user.role, "value") else str(user.role))
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=TokenResponse(access_token=token, token_type="bearer")
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Register a new inspector or officer account."""
    # Rate limit registrations per IP (5 per hour) to stop scripted abuse
    check_rate_limit(f"register:{_client_ip(request)}", max_requests=5, window_seconds=3600)

    # Sanitize free-text fields before persistence
    name = _sanitize(req.name, 255)
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required")

    try:
        user = await register_user(
            db=db,
            name=name,
            password=req.password,
            email=_sanitize(req.email, 255),
            mobile=_sanitize(req.mobile, 20),
            role=req.role if req.role in ("INSPECTOR", "SENIOR_OFFICER", "ADMIN") else "INSPECTOR",
            designation=_sanitize(req.designation, 255),
            office=_sanitize(req.office, 255),
            district=_sanitize(req.district, 255),
            state=_sanitize(req.state, 255),
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to a server error. Please try again later."
        )

    token = create_access_token(str(user.id), user.role.value if hasattr(user.role, "value") else str(user.role))
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=TokenResponse(access_token=token, token_type="bearer")
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Retrieve profile of authenticated user."""
    return UserResponse.model_validate(current_user)
