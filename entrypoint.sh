#!/bin/sh
set -e

cd /app
echo "Running database migrations..."
uv run --no-sync alembic -c /app/alembic.ini upgrade head

echo "Starting Uvicorn server..."
exec "$@"