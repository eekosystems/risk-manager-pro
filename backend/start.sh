#!/bin/sh
set -e

echo "Running database migrations..."
python -m alembic upgrade head || {
    echo "Migration failed, attempting to stamp current state..."
    python -m alembic stamp head
}

echo "Starting application server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
