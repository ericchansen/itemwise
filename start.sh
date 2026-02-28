#!/bin/sh
set -e

# Wait for PostgreSQL to be reachable before running migrations
echo "Waiting for database..."
MAX_WAIT=30
INTERVAL=2
ELAPSED=0
DB_READY=0

while [ "$ELAPSED" -lt "$MAX_WAIT" ]; do
  if python -c "
import socket, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
s.connect((os.environ.get('POSTGRES_HOST', 'localhost'), int(os.environ.get('POSTGRES_PORT', '5432'))))
s.close()
" 2>/dev/null; then
    echo "Database ready!"
    DB_READY=1
    break
  fi
  echo "Database not ready, retrying in ${INTERVAL}s... (${ELAPSED}/${MAX_WAIT}s)"
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [ "$DB_READY" -eq 0 ]; then
  echo "Database not available after ${MAX_WAIT}s, starting anyway"
fi

echo "Checking database migration state..."
python fix_migration.py || echo "Migration state check completed (non-fatal errors ignored)"

echo "Running database migrations..."
python -m alembic upgrade head || echo "Migration failed or already up to date"

echo "Starting application..."
exec python -m uvicorn itemwise.api:app --host 0.0.0.0 --port 8080
