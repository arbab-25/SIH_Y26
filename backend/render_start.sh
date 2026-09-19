#!/usr/bin/env bash
# Render startup script for CODE MAZE backend
# Runs DB migrations, seeds data, then starts the API server
set -e

if [ -z "${DATABASE_URL:-}" ] || [ -z "${DATABASE_URL_SYNC:-}" ]; then
  echo "ERROR: DATABASE_URL and DATABASE_URL_SYNC must be configured as Render secret environment variables."
  exit 1
fi

case "${DATABASE_URL}" in
  DATABASE_URL=*|DATABASE_URL_SYNC=*|*YOUR-NEON-HOST*|*USER:PASSWORD*)
    echo "ERROR: DATABASE_URL must contain only a real Neon connection-string value, not a dotenv assignment or example placeholder."
    exit 1
    ;;
esac

case "${DATABASE_URL_SYNC}" in
  DATABASE_URL=*|DATABASE_URL_SYNC=*|*YOUR-NEON-HOST*|*USER:PASSWORD*)
    echo "ERROR: DATABASE_URL_SYNC must contain only a real Neon connection-string value, not a dotenv assignment or example placeholder."
    exit 1
    ;;
esac

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Seeding database..."
python seed/seed_db.py || echo "Seed already applied or skipped."

echo "==> Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
