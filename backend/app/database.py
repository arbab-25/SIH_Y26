"""SQLAlchemy async engine and session factory."""

import ssl
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# "require" semantics: encrypt the connection without certificate verification
# (works for Neon, Render Postgres, and self-signed internal endpoints alike).
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

engine_kwargs: dict[str, Any] = {"echo": settings.DEBUG}
if not is_sqlite:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    })
    # Managed Postgres (Neon/Render) requires TLS. asyncpg does not accept the
    # libpq 'sslmode' URL parameter, so SSL is configured explicitly here with
    # a real SSLContext (deterministic across driver versions).
    if "localhost" not in settings.DATABASE_URL and "127.0.0.1" not in settings.DATABASE_URL:
        engine_kwargs["connect_args"] = {"ssl": _ssl_ctx}
    else:
        engine_kwargs["connect_args"] = {"ssl": False}

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
