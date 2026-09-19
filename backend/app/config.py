"""Application configuration loaded from environment variables."""

import re
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """All configuration is loaded from environment variables or .env file."""

    # Database (defaults to local SQLite for instant zero-dependency run; override with PostgreSQL / Neon in .env)
    DATABASE_URL: str = "sqlite+aiosqlite:///./codemaze.db"
    DATABASE_URL_SYNC: str = "sqlite:///./codemaze.db"

    # Redis (optional)
    REDIS_URL: Optional[str] = None

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production-long-secure-key-64-bits-codemaze"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # SMTP
    SMTP_HOST: str = "smtp-relay.brevo.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@codemaze.app"

    # Email & Escalations
    REPORT_RECIPIENT_EMAIL: str = "arbab.momin.2008@gmail.com"
    RESEND_API_KEY: Optional[str] = None
    MAIL_FROM: str = "CODE MAZE <onboarding@resend.dev>"

    # Storage
    STORAGE_BACKEND: str = "local"  # "local" or "supabase"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET: str = "codemaze-uploads"
    LOCAL_UPLOAD_DIR: str = "uploads"

    # OCR
    OCR_CONFIDENCE_THRESHOLD: float = 0.75
    OCR_ENGINE: str = "tesseract"  # "tesseract" or "paddleocr"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # App
    APP_NAME: str = "CODE MAZE"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECURE_COOKIES: bool = True
    ENVIRONMENT: str = "development"

    # Rate limiting
    RATE_LIMIT_SCANS_PER_MIN: int = 30
    GUEST_FREE_SCAN_LIMIT: int = 3
    GUEST_FREE_SCANS: int = 3

    # Uploads
    MAX_IMAGES_PER_SCAN: int = 5

    @field_validator("DATABASE_URL", "DATABASE_URL_SYNC", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Reject copied dotenv assignments and placeholder URLs before SQLAlchemy starts."""
        url = str(value).strip()
        if url.startswith("DATABASE_URL=") or url.startswith("DATABASE_URL_SYNC="):
            raise ValueError(
                "Set the Render environment variable to the connection-string value only; "
                "do not include DATABASE_URL= or DATABASE_URL_SYNC=."
            )
        if "YOUR-NEON-HOST" in url or "USER:PASSWORD" in url:
            raise ValueError(
                "Replace the example database URL with the real Neon connection string from Neon Connection Details."
            )
        return url

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def use_asyncpg_for_runtime(cls, url: str) -> str:
        """Neon emits postgresql:// URLs; FastAPI needs SQLAlchemy's asyncpg dialect.

        asyncpg rejects the libpq-style 'sslmode' query parameter (this broke every
        Neon/Render deployment with: connect() got an unexpected keyword argument
        'sslmode'), so we strip it here and force SSL in database.py for remote hosts.
        """
        url = re.sub(r"([?&])sslmode=[^&]+", lambda m: "?" if m.group(1) == "?" else "", url).rstrip("?")
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @field_validator("DATABASE_URL_SYNC", mode="after")
    @classmethod
    def strip_sslmode_sync(cls, url: str) -> str:
        """Strip libpq sslmode from the Alembic sync URL (pg8000 rejects it too)."""
        return re.sub(r"([?&])sslmode=[^&]+", lambda m: "?" if m.group(1) == "?" else "", url).rstrip("?")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
