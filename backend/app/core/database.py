import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

_db_url = settings.database_url
# Container Apps may not resolve VNet private DNS — use IP directly if provided
_private_ip = os.environ.get("DB_PRIVATE_IP", "")
if _private_ip and _db_url:
    last_at = _db_url.rfind("@")
    if last_at != -1:
        colon_after = _db_url.index(":", last_at)
        _db_url = _db_url[: last_at + 1] + _private_ip + _db_url[colon_after:]

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class OrganizationMixin:
    organization_id: Mapped[uuid.UUID] = mapped_column(index=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            raise
