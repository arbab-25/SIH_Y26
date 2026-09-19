"""Pydantic schemas for auth endpoints."""

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
import re


class RegisterRequest(BaseModel):
    """Registration with email OR mobile + password."""
    name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    password: str
    role: str = "INSPECTOR"
    designation: Optional[str] = None
    office: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v and not re.match(r"^[^@]+@[^@]+\.[^@]+$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v):
        if v and not re.match(r"^[6-9]\d{9}$", v):
            raise ValueError("Invalid Indian mobile number (10 digits, starts 6-9)")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    def model_post_init(self, __context):
        if not self.email and not self.mobile:
            raise ValueError("Either email or mobile number is required")


class LoginRequest(BaseModel):
    """Login with email OR mobile (single field 'identifier')."""
    identifier: str  # email or mobile
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    role: str
    designation: Optional[str] = None
    office: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class AuthResponse(BaseModel):
    user: UserResponse
    token: TokenResponse
