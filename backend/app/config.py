"""Application configuration loaded from environment variables."""

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings

# libpq-only query params that managed-Postgres providers (Neon/Render/Supabase)
# append to connection strings. asyncpg rejects them with
# "TypeError: connect() got an unexpected keyword argument ...".
# Neon's copy-string ships at least: sslmode=require & channel_binding=require.
LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding", "gssencmode")


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

    # Storage — "local" (default) or "s3" (any S3-compatible API: AWS S3,
    # Cloudflare R2 10GB free tier, Backblaze B2, MinIO). Credentials via env only.
    STORAGE_BACKEND: str = "local"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET: str = "codemaze-uploads"
    LOCAL_UPLOAD_DIR: str = "uploads"

    # OCR
    OCR_CONFIDENCE_THRESHOLD: float = 0.75
    OCR_ENGINE: str = "tesseract"  # "tesseract" or "paddleocr"
    # Longest side a label image is downscaled to before OCR. The OCR models work
    # fine at this size; beyond it, inference memory and time explode on small
    # instances (Render free tier OOM-kills the worker mid-request -> HTTP 502).
    OCR_MAX_DIMENSION: int = 1200
    # Intra-op threads for the ONNX OCR runtime. On tiny instances (0.1 CPU)
    # multi-threaded ONNX starves the event loop: health checks time out and
    # the platform restarts the service, orphaning in-flight scans. 1 thread
    # is slower per image but keeps the service responsive.
    OCR_THREADS: int = 1
    # Phase-1 accuracy pipeline (deskew + NL-means denoise + CLAHE + bounded
    # upscale) before OCR. Set false only for A/B benchmarking.
    OCR_ENHANCE: bool = True
    # Tesseract language packs for OCR (English + Hindi per Phase 1). Falls
    # back to English-only at inference time when a pack is missing on the host.
    OCR_LANGUAGES: str = "eng+hin"

    # CORS – defaults include the deployed frontend so a missing env var can never lock out users
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,"
        "https://codemaze-frontend-m6f0.onrender.com"
    )

    # App
    APP_NAME: str = "CODE MAZE"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECURE_COOKIES: bool = True
    ENVIRONMENT: str = "development"

    # Rate limiting (guest mode removed: all scans require a signed-in inspector)
    RATE_LIMIT_SCANS_PER_MIN: int = 30

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

    # libpq-only query params that managed-Postgres providers (Neon/Render/Supabase)
    # append to connection strings. asyncpg rejects them with
    # "TypeError: connect() got an unexpected keyword argument ...".
    # Neon's copy-string ships at least: sslmode=require & channel_binding=require.
    # (Parameter list lives in module-level LIBPQ_ONLY_PARAMS.)

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def use_asyncpg_for_runtime(cls, url: str) -> str:
        """Neon emits postgresql:// URLs; FastAPI needs SQLAlchemy's asyncpg dialect.

        asyncpg rejects libpq-style query parameters (this broke every Neon/Render
        deployment with: connect() got an unexpected keyword argument), so they are
        stripped here and TLS is forced in database.py for remote hosts.
        """
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return cls._strip_libpq_params(url)

    @field_validator("DATABASE_URL_SYNC", mode="after")
    @classmethod
    def strip_libpq_extras_sync(cls, url: str) -> str:
        """Strip libpq-only extras from the Alembic sync URL (harmless for pg8000/psycopg2)."""
        return cls._strip_libpq_params(url)

    @classmethod
    def _strip_libpq_params(cls, url: str) -> str:
        """Remove libpq-only query params from a connection URL (query-aware)."""
        if "?" not in url:
            return url
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
        parts = urlsplit(url)
        kept = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in LIBPQ_ONLY_PARAMS
        ]
        query = urlencode(kept)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
