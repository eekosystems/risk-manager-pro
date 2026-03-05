from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse
from app.schemas.user import UserOrgMembership, UserProfileResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=DataResponse[UserProfileResponse])
async def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[UserProfileResponse]:
    correlation_id = getattr(request.state, "correlation_id", "")

    stmt = (
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.is_active.is_(True),
        )
        .options(selectinload(OrganizationMembership.organization))
    )
    result = await db.execute(stmt)
    memberships = list(result.scalars().all())

    org_memberships = [
        UserOrgMembership(
            organization_id=m.organization_id,
            organization_name=m.organization.name,
            role=m.role,
            is_active=m.is_active,
        )
        for m in memberships
    ]

    profile = UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        is_platform_admin=current_user.is_platform_admin,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        organizations=org_memberships,
    )

    return DataResponse(
        data=profile,
        meta=MetaResponse(request_id=correlation_id),
    )
