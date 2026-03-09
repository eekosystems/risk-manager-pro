import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User


class MembershipRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add_member(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role: MembershipRole = MembershipRole.VIEWER,
        invited_by: uuid.UUID | None = None,
    ) -> OrganizationMembership:
        membership = OrganizationMembership(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            invited_by=invited_by,
        )
        self._db.add(membership)
        await self._db.flush()
        return membership

    async def get_membership(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> OrganizationMembership | None:
        stmt = select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_members(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[OrganizationMembership], int]:
        count_stmt = (
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.is_active.is_(True),
            )
        )
        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.is_active.is_(True),
            )
            .options(selectinload(OrganizationMembership.user))
            .order_by(OrganizationMembership.created_at)
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total

    async def update_role(
        self, user_id: uuid.UUID, organization_id: uuid.UUID, role: MembershipRole
    ) -> OrganizationMembership | None:
        membership = await self.get_membership(user_id, organization_id)
        if not membership:
            return None
        membership.role = role
        await self._db.flush()
        return membership

    async def remove_member(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        membership = await self.get_membership(user_id, organization_id)
        if not membership:
            return False
        membership.is_active = False
        await self._db.flush()
        return True

    async def find_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
