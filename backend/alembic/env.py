"""Alembic env.py — connects migrations to our SQLAlchemy models.

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add the backend directory to the path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
# Import all models so Alembic can detect them
from app.models import *  # noqa: F401, F403

from app.config import settings

config = context.config

# Override sqlalchemy.url with environment variable if available.
# pg8000 is the sync driver in this project (psycopg2 is deliberately not
# installed — see requirements.txt). Do not switch to the bare postgresql://
# psycopg2 dialect.
database_url = settings.DATABASE_URL_SYNC
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Return connect_args for a remote Postgres (Neon/Render) TLS connection.

    pg8000's connect() parameter is 'ssl_context' (an ssl.SSLContext) — it does
    NOT accept libpq-style 'sslmode' or a bare 'ssl' kwarg. Mirrors
    app/database.py (CERT_NONE so self-signed and managed-Postgres TLS both
    work without certificate verification).
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
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
