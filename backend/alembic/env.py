"""Alembic env.py — connects migrations to our SQLAlchemy models."""

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

# Override sqlalchemy.url with environment variable if available
database_url = settings.DATABASE_URL_SYNC
if database_url:
    # Switch from pg8000 to psycopg2 to fix Neon SSL issues natively
    if "postgresql+pg8000://" in database_url:
        database_url = database_url.replace("postgresql+pg8000://", "postgresql://")
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


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
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
