import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_audit_logger, get_current_user, require_platform_admin
from app.core.exceptions import NotFoundError, ValidationError
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse
from app.schemas.user import (
    SetPlatformAdminRequest,
    UserOrgMembership,
    UserProfileResponse,
    UserResponse,
)
from app.services.audit import AuditLogger

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


@router.patch("/{user_id}/platform-admin", response_model=DataResponse[UserResponse])
async def set_platform_admin(
    user_id: uuid.UUID,
    payload: SetPlatformAdminRequest,
    request: Request,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[UserResponse]:
    """Grant or revoke platform administration.

    A platform admin can read every tenant's data and change the AI
    configuration for all of them, so the two ways to strand the platform are
    both refused: you cannot change your own flag, and the last active platform
    admin cannot be demoted.
    """
    if user_id == current_user.id:
        raise ValidationError(
            "You cannot change your own platform administrator access. Ask another platform admin."
        )

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise NotFoundError("User", str(user_id))

    if not payload.is_platform_admin and target.is_platform_admin:
        remaining = await db.execute(
            select(User).where(
                User.is_platform_admin.is_(True),
                User.id != target.id,
                User.is_active.is_(True),
            )
        )
        if not list(remaining.scalars().all()):
            raise ValidationError(
                "This is the last active platform administrator and cannot be removed"
            )

    target.is_platform_admin = payload.is_platform_admin
    await db.flush()

    await audit.log(
        action="user.platform_admin_granted"
        if payload.is_platform_admin
        else "user.platform_admin_revoked",
        user=current_user,
        resource_type="user",
        resource_id=str(user_id),
    )

    correlation_id = getattr(request.state, "correlation_id", "")
    return DataResponse(
        data=UserResponse.model_validate(target),
        meta=MetaResponse(request_id=correlation_id),
    )
