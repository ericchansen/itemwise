#!/bin/sh
set -e

echo "Checking database migration state..."
python fix_migration.py || echo "Migration state check completed (non-fatal errors ignored)"

echo "Running database migrations..."
python -m alembic upgrade head || echo "Migration failed or already up to date"

echo "Starting application..."
exec python -m uvicorn itemwise.api:app --host 0.0.0.0 --port 8080
