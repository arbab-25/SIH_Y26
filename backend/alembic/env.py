"""Alembic env.py — connects migrations to our SQLAlchemy models.

Runs with the pg8000 sync driver: psycopg2 is deliberately not installed (see
requirements.txt), so the sync URL is normalized onto postgresql+pg8000://
here. Remote Postgres (Neon/Render) is reached over TLS via pg8000's
'ssl_context' connect argument.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

import os
import sys

# Add the backend directory to the path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base

# Import all models so Alembic can read the full metadata
from app.models import *  # noqa: F401, F403

from app.config import settings

config = context.config

# ------------------------------------------------------------------
# Sync URL: always resolve to the pg8000 dialect.
# On Render, DATABASE_URL_SYNC is a bare postgresql:// Neon copy-string;
# SQLAlchemy would default that to the psycopg2 dialect (not installed)
# and crash migrations with ModuleNotFoundError. app/config.py only
# strips libpq params from the sync URL — it does not rewrite its
# dialect — so the normalization happens here.
# ------------------------------------------------------------------
database_url = settings.DATABASE_URL_SYNC

LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding", "gssencmode")

if database_url.startswith("postgresql://") and "+" not in database_url:
    database_url = "postgresql+pg8000://" + database_url[len("postgresql://"):]

# Belt-and-braces: strip libpq-only query params (required for Neon-style
# URLs; harmless when the URL has no query string).
if database_url.startswith("postgresql"):
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

    parts = urlsplit(database_url)
    if parts.query:
        kept = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in LIBPQ_ONLY_PARAMS
        ]
        database_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment)
        )

if database_url:
    # configparser interpolation requires % to be escaped as %%.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _remote_ssl_config(url: str) -> dict:
    """Return connect_args for a remote Postgres TLS connection.

    pg8000's connect() parameter is 'ssl_context' (an ssl.SSLContext) — it
    does not accept libpq-style 'sslmode'. Mirrors app/database.py: CERT_NONE
    so managed Postgres (Neon/Render) TLS works without certificate files.
    """
    if "localhost" in url or "127.0.0.1" in url:
        return {}
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return {"ssl_context": ctx}


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = config.get_main_option("sqlalchemy.url") or ""
    # Build the engine directly instead of engine_from_config: connect_args
    # with a non-serializable SSLContext cannot round-trip through the
    # configparser section, and a '%' in the password would break
    # interpolation even with the %% escape above.
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=_remote_ssl_config(url),
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
