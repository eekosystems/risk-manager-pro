import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import OrganizationMembership
from app.repositories.membership import MembershipRepository

# Re-export for backward compatibility
__all__ = ["MembershipRepository", "OrganizationRepository"]


class OrganizationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        name: str,
        slug: str,
        is_platform: bool = False,
        created_by: uuid.UUID | None = None,
    ) -> Organization:
        org = Organization(
            name=name,
            slug=slug,
            is_platform=is_platform,
            created_by=created_by,
        )
        self._db.add(org)
        await self._db.flush()
        return org

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        stmt = select(Organization).where(Organization.id == org_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 50) -> tuple[list[Organization], int]:
        count_stmt = select(func.count()).select_from(Organization)
        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = select(Organization).order_by(Organization.name).offset(skip).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_for_user(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[Organization]:
        stmt = (
            select(Organization)
            .join(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.is_active.is_(True),
                Organization.status == OrganizationStatus.ACTIVE,
            )
            .order_by(Organization.name)
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        org_id: uuid.UUID,
        name: str | None = None,
        status: OrganizationStatus | None = None,
        settings_json: dict[str, Any] | None = None,
    ) -> Organization | None:
        org = await self.get_by_id(org_id)
        if not org:
            return None
        if name is not None:
            org.name = name
        if status is not None:
            org.status = status
        if settings_json is not None:
            org.settings_json = settings_json
        await self._db.flush()
        return org
