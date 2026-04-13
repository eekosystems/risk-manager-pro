import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps.auth import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User


async def get_current_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_organization_id: str | None = Header(None),
) -> Organization:
    if x_organization_id:
        org_id = uuid.UUID(x_organization_id)
        stmt = select(Organization).where(
            Organization.id == org_id,
            Organization.status == OrganizationStatus.ACTIVE,
        )
        result = await db.execute(stmt)
        org = result.scalar_one_or_none()
        if not org:
            raise NotFoundError("Organization", x_organization_id)

        if not current_user.is_platform_admin:
            membership_stmt = select(OrganizationMembership).where(
                OrganizationMembership.user_id == current_user.id,
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.is_active.is_(True),
            )
            membership_result = await db.execute(membership_stmt)
            if not membership_result.scalar_one_or_none():
                raise ForbiddenError("You are not a member of this organization")

        return org

    # No header: default to user's first active org
    membership_stmt = (
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.is_active.is_(True),
        )
        .options(selectinload(OrganizationMembership.organization))
        .limit(1)
    )
    membership_result = await db.execute(membership_stmt)
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise ForbiddenError("You are not a member of any organization")
    return membership.organization


def require_org_role(*allowed_roles: MembershipRole) -> Callable[..., Awaitable[User]]:
    async def _check_org_role(
        current_user: User = Depends(get_current_user),
        organization: Organization = Depends(get_current_organization),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        from app.core.config import settings

        if current_user.is_platform_admin:
            return current_user

        stmt = select(OrganizationMembership).where(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.is_active.is_(True),
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership or membership.role not in allowed_roles:
            if not settings.enforce_rbac:
                return current_user
            raise ForbiddenError(
                f"Requires one of roles: {', '.join(r.value for r in allowed_roles)}"
            )
        return current_user

    return _check_org_role


require_analyst_or_above = require_org_role(MembershipRole.ORG_ADMIN, MembershipRole.ANALYST)
require_any_member = require_org_role(
    MembershipRole.ORG_ADMIN, MembershipRole.ANALYST, MembershipRole.VIEWER
)


async def require_platform_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_platform_admin:
        raise ForbiddenError("Platform admin access required")
    return current_user
