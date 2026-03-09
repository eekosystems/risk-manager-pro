import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import OrganizationSettings


class SettingsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(
        self, organization_id: uuid.UUID, category: str
    ) -> OrganizationSettings | None:
        stmt = select(OrganizationSettings).where(
            OrganizationSettings.organization_id == organization_id,
            OrganizationSettings.category == category,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self, organization_id: uuid.UUID
    ) -> list[OrganizationSettings]:
        stmt = select(OrganizationSettings).where(
            OrganizationSettings.organization_id == organization_id,
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        organization_id: uuid.UUID,
        category: str,
        settings_json: dict[str, Any],
        updated_by: uuid.UUID,
    ) -> OrganizationSettings:
        existing = await self.get(organization_id, category)
        if existing:
            existing.settings_json = settings_json
            existing.updated_by = updated_by
            await self._db.flush()
            return existing

        row = OrganizationSettings(
            organization_id=organization_id,
            category=category,
            settings_json=settings_json,
            updated_by=updated_by,
        )
        self._db.add(row)
        await self._db.flush()
        return row
