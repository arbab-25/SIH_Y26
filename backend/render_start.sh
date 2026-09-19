#!/usr/bin/env bash
# Render startup script for CODE MAZE backend
# Runs DB migrations, seeds data, then starts the API server
set -e

# The runtime needs both URLs; derive one from the other if only one is set.
# (The config validators strip libpq 'sslmode' and switch dialects as needed.)
if [ -z "${DATABASE_URL:-}" ] && [ -n "${DATABASE_URL_SYNC:-}" ]; then
  export DATABASE_URL="$DATABASE_URL_SYNC"
fi
if [ -z "${DATABASE_URL_SYNC:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
  export DATABASE_URL_SYNC="$DATABASE_URL"
fi

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

echo "==> Waiting for database to accept connections..."
for i in $(seq 1 30); do
  if python -c "
import os, sys
try:
    import sqlalchemy
    url = os.environ['DATABASE_URL_SYNC']
    eng = sqlalchemy.create_engine(url, connect_args={'sslmode': 'require'} if 'sslmode' not in url and 'localhost' not in url and '127.0.0.1' not in url else {})
    with eng.connect() as c:
        c.exec_driver_sql('SELECT 1')
except Exception as e:
    sys.exit(1)
sys.exit(0)
" 2>/dev/null; then
    echo "Database is ready."
    break
  fi
  echo "  Database not ready yet (attempt $i/30), retrying in 2s..."
  sleep 2
done

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Seeding database..."
python seed/seed_db.py || echo "Seed already applied or skipped."

echo "==> Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
