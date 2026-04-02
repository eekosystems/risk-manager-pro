#!/bin/sh
set -e

echo "Running database migrations..."
python -m alembic upgrade head || {
    echo "WARNING: Migration failed. Stamping current state to allow startup." >&2
    echo "WARNING: Review migration state manually — data may be out of sync." >&2
    python -m alembic stamp head
}

echo "Starting application server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
