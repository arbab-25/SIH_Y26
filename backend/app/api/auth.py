"""Authentication API Router — Register, Login (email or mobile), Me profile."""

from fastapi import APIRouter, Depends, HTTPException, status
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

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login using either email OR 10-digit mobile number + password."""
    user = await authenticate_user(db, req.identifier, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/mobile or password"
        )

    token = create_access_token(str(user.id), user.role.value if hasattr(user.role, 'value') else str(user.role))
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=TokenResponse(access_token=token, token_type="bearer")
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new inspector or officer account."""
    try:
        user = await register_user(
            db=db,
            name=req.name,
            password=req.password,
            email=req.email,
            mobile=req.mobile,
            role=req.role,
            designation=req.designation,
            office=req.office,
            district=req.district,
            state=req.state,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Registration error: {str(e)}")

    token = create_access_token(str(user.id), user.role.value if hasattr(user.role, 'value') else str(user.role))
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=TokenResponse(access_token=token, token_type="bearer")
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Retrieve profile of authenticated user."""
    return UserResponse.model_validate(current_user)
