#!/bin/sh
set -e

echo "Running database migrations..."
uv run --no-sync alembic upgrade head

echo "Starting Uvicorn server..."
exec "$@"