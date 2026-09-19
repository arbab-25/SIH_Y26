#!/usr/bin/env bash
# Render startup script for CODE MAZE backend
# Runs DB migrations, seeds data, then starts the API server
set -e

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Seeding database..."
python seed/seed_db.py || echo "Seed already applied or skipped."

echo "==> Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
