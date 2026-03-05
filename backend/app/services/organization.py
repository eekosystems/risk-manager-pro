import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.repositories.organization import OrganizationRepository
from app.schemas.organization import MemberResponse

logger = structlog.get_logger(__name__)


def _membership_to_response(membership: OrganizationMembership) -> MemberResponse:
    return MemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        organization_id=membership.organization_id,
        role=membership.role,
        is_active=membership.is_active,
        email=membership.user.email if membership.user else "",
        display_name=membership.user.display_name if membership.user else "",
        created_at=membership.created_at,
    )


class OrganizationService:
    def __init__(self, db: AsyncSession) -> None:
        self._org_repo = OrganizationRepository(db)
        self._membership_repo = MembershipRepository(db)

    async def create_organization(
        self,
        name: str,
        slug: str,
        created_by: uuid.UUID,
        is_platform: bool = False,
    ) -> Organization:
        existing = await self._org_repo.get_by_slug(slug)
        if existing:
            raise ConflictError(f"Organization with slug '{slug}' already exists")

        org = await self._org_repo.create(
            name=name,
            slug=slug,
            is_platform=is_platform,
            created_by=created_by,
        )
        logger.info("organization_created", org_id=str(org.id), slug=slug)
        return org

    async def get_organization(self, org_id: uuid.UUID) -> Organization:
        org = await self._org_repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization", str(org_id))
        return org

    async def get_organization_with_access_check(
        self, org_id: uuid.UUID, user: User
    ) -> Organization:
        org = await self.get_organization(org_id)
        if not user.is_platform_admin:
            membership = await self._membership_repo.get_membership(user.id, org_id)
            if not membership or not membership.is_active:
                raise ForbiddenError("You are not a member of this organization")
        return org

    async def verify_membership_or_admin(
        self, org_id: uuid.UUID, user: User
    ) -> None:
        if user.is_platform_admin:
            return
        membership = await self._membership_repo.get_membership(user.id, org_id)
        if not membership or not membership.is_active:
            raise ForbiddenError("You are not a member of this organization")

    async def list_organizations(
        self,
        user: User,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Organization]:
        if user.is_platform_admin:
            orgs, _ = await self._org_repo.list_all(skip, limit)
            return orgs
        return await self._org_repo.list_for_user(user.id, skip, limit)

    async def update_organization(
        self,
        org_id: uuid.UUID,
        name: str | None = None,
        status: OrganizationStatus | None = None,
        settings_json: dict[str, object] | None = None,
    ) -> Organization:
        org = await self._org_repo.update(org_id, name, status, settings_json)
        if not org:
            raise NotFoundError("Organization", str(org_id))
        logger.info("organization_updated", org_id=str(org_id))
        return org

    async def add_member(
        self,
        organization_id: uuid.UUID,
        role: MembershipRole,
        invited_by: uuid.UUID,
        user_id: uuid.UUID | None = None,
        email: str | None = None,
    ) -> OrganizationMembership:
        if not user_id and not email:
            raise ValidationError("Either user_id or email is required")

        if email and not user_id:
            user = await self._membership_repo.find_user_by_email(email)
            if not user:
                raise NotFoundError("User", email)
            user_id = user.id

        if user_id is None:
            raise ValidationError("Could not resolve user_id from email")

        existing = await self._membership_repo.get_membership(user_id, organization_id)
        if existing and existing.is_active:
            raise ConflictError("User is already a member of this organization")

        if existing and not existing.is_active:
            existing.is_active = True
            existing.role = role
            return existing

        membership = await self._membership_repo.add_member(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            invited_by=invited_by,
        )
        logger.info(
            "member_added",
            org_id=str(organization_id),
            user_id=str(user_id),
            role=role.value,
        )
        return membership

    async def add_member_and_build_response(
        self,
        organization_id: uuid.UUID,
        role: MembershipRole,
        invited_by: uuid.UUID,
        user_id: uuid.UUID | None = None,
        email: str | None = None,
    ) -> MemberResponse:
        membership = await self.add_member(
            organization_id=organization_id,
            role=role,
            invited_by=invited_by,
            user_id=user_id,
            email=email,
        )
        return _membership_to_response(membership)

    async def list_members(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[OrganizationMembership], int]:
        return await self._membership_repo.list_members(organization_id, skip, limit)

    async def list_members_response(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[MemberResponse]:
        members, _ = await self.list_members(organization_id, skip, limit)
        return [_membership_to_response(m) for m in members]

    async def update_member_role(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        role: MembershipRole,
    ) -> OrganizationMembership:
        membership = await self._membership_repo.update_role(user_id, organization_id, role)
        if not membership:
            raise NotFoundError("Membership", f"{user_id}/{organization_id}")
        logger.info(
            "member_role_updated",
            org_id=str(organization_id),
            user_id=str(user_id),
            role=role.value,
        )
        return membership

    async def update_member_role_and_build_response(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        role: MembershipRole,
    ) -> MemberResponse:
        membership = await self.update_member_role(organization_id, user_id, role)
        return _membership_to_response(membership)

    async def remove_member(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        removed = await self._membership_repo.remove_member(user_id, organization_id)
        if not removed:
            raise NotFoundError("Membership", f"{user_id}/{organization_id}")
        logger.info(
            "member_removed",
            org_id=str(organization_id),
            user_id=str(user_id),
        )
