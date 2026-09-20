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
DB_READY=0
DB_LAST_ERROR=""
set +e
for i in $(seq 1 30); do
  DB_LAST_ERROR=$(python -c "
import os, sys
try:
    import sqlalchemy
    url = os.environ['DATABASE_URL_SYNC']
    # Normalize to a sqlalchemy dialect form it recognises. pg8000 is the sync
    # driver in this project — psycopg2 is deliberately NOT installed (see
    # requirements.txt), so 'postgresql://' (psycopg2) must never be used here.
    if url.startswith('postgresql://') and '+' not in url:
        url = 'postgresql+pg8000://' + url[len('postgresql://'):]
    connect_args = {}
    if 'localhost' not in url and '127.0.0.1' not in url:
        connect_args['sslmode'] = 'require'
    eng = sqlalchemy.create_engine(url, connect_args=connect_args)
    with eng.connect() as c:
        c.exec_driver_sql('SELECT 1')
    sys.exit(0)
except Exception as e:
    print(f'{type(e).__name__}: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)
  if [ $? -eq 0 ]; then
    echo "Database is ready."
    DB_READY=1
    break
  fi
  echo "  Database not ready yet (attempt $i/30). Error: $DB_LAST_ERROR"
  sleep 2
done
set -e

if [ "$DB_READY" -ne 1 ]; then
  echo "ERROR: Database never became reachable. Last error: $DB_LAST_ERROR"
  echo "HINT: verify DATABASE_URL / DATABASE_URL_SYNC point at the live Neon host,"
  echo "      and that the Neon branch is not suspended or deleted."
  exit 1
fi

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Seeding database..."
python seed/seed_db.py || echo "Seed already applied or skipped."

echo "==> Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
