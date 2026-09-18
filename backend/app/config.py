"""Application configuration loaded from environment variables."""

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

    # Report
    REPORT_RECIPIENT_EMAIL: str = "arbab.momin.2008@gmail.com"

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

    # Rate limiting
    RATE_LIMIT_SCANS_PER_MIN: int = 30
    GUEST_FREE_SCAN_LIMIT: int = 3

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
