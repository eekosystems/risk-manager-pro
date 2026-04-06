#!/bin/sh

# Reset stale alembic stamp if core tables are missing (e.g. after stamp-without-migrate)
python -c "
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def check():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            \"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users')\"
        ))
        has_users = result.scalar()
        if not has_users:
            await conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
            await conn.commit()
            print('Alembic version reset — tables missing, will re-migrate')
        else:
            print('Tables exist — skipping alembic reset')
    await engine.dispose()

asyncio.run(check())
" || echo "WARNING: Alembic reset check failed, continuing..." >&2

echo "Running database migrations..."
python -m alembic upgrade head || {
    echo "WARNING: Migration failed. Stamping current state to allow startup." >&2
    echo "WARNING: Review migration state manually — data may be out of sync." >&2
    python -m alembic stamp head || echo "WARNING: Stamp also failed, starting anyway..." >&2
}

echo "Starting application server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
