"""Tests for organization service."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.services.organization import OrganizationService
from tests.conftest import make_test_organization, make_test_user


@pytest.fixture
def org_service() -> OrganizationService:
    db = AsyncMock()
    return OrganizationService(db=db)


@pytest.mark.asyncio
async def test_create_organization(org_service: OrganizationService) -> None:
    org = make_test_organization(slug="test-create")
    creator = make_test_user(is_platform_admin=True)

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_slug.return_value = None
    org_service._org_repo.create.return_value = org

    result = await org_service.create_organization(
        name="Test Create Org",
        slug="test-create",
        created_by=creator.id,
    )

    assert result.slug == "test-create"
    org_service._org_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_organization_duplicate_slug(org_service: OrganizationService) -> None:
    existing_org = make_test_organization(slug="duplicate-slug")
    creator = make_test_user(is_platform_admin=True)

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_slug.return_value = existing_org

    with pytest.raises(ConflictError, match="slug"):
        await org_service.create_organization(
            name="Duplicate Org",
            slug="duplicate-slug",
            created_by=creator.id,
        )


@pytest.mark.asyncio
async def test_get_organization(org_service: OrganizationService) -> None:
    org = make_test_organization()
    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = org

    result = await org_service.get_organization(org.id)
    assert result.id == org.id


@pytest.mark.asyncio
async def test_get_organization_not_found(org_service: OrganizationService) -> None:
    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundError):
        await org_service.get_organization(uuid.uuid4())


@pytest.mark.asyncio
async def test_add_member(org_service: OrganizationService) -> None:
    org = make_test_organization()
    user = make_test_user()
    inviter = make_test_user(is_platform_admin=True, email="inviter@example.com")
    membership = OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.ANALYST,
        is_active=True,
    )

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = org
    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.get_membership.return_value = None
    org_service._membership_repo.add_member.return_value = membership

    result = await org_service.add_member(
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ANALYST,
        invited_by=inviter.id,
    )

    assert result.role == MembershipRole.ANALYST
    org_service._membership_repo.add_member.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_members(org_service: OrganizationService) -> None:
    org = make_test_organization()
    memberships = [
        OrganizationMembership(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            organization_id=org.id,
            role=MembershipRole.ANALYST,
            is_active=True,
        ),
    ]

    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.list_members.return_value = (memberships, 1)

    result, total = await org_service.list_members(org.id)
    assert len(result) == 1
    assert total == 1


@pytest.mark.asyncio
async def test_update_member_role(org_service: OrganizationService) -> None:
    org = make_test_organization()
    user = make_test_user()
    updated_membership = OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.ORG_ADMIN,
        is_active=True,
    )

    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.update_role.return_value = updated_membership

    result = await org_service.update_member_role(
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ORG_ADMIN,
    )

    assert result.role == MembershipRole.ORG_ADMIN


@pytest.mark.asyncio
async def test_remove_member(org_service: OrganizationService) -> None:
    org = make_test_organization()
    user = make_test_user()

    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.remove_member.return_value = True

    await org_service.remove_member(
        organization_id=org.id,
        user_id=user.id,
    )

    org_service._membership_repo.remove_member.assert_awaited_once_with(
        user.id, org.id
    )


@pytest.mark.asyncio
async def test_remove_member_not_found(org_service: OrganizationService) -> None:
    org = make_test_organization()
    user = make_test_user()

    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.remove_member.return_value = False

    with pytest.raises(NotFoundError, match="Membership"):
        await org_service.remove_member(
            organization_id=org.id,
            user_id=user.id,
        )


@pytest.mark.asyncio
async def test_list_organizations_as_admin(org_service: OrganizationService) -> None:
    """Platform admin should see all orgs via list_all."""
    admin = make_test_user(is_platform_admin=True, email="admin@example.com")
    orgs = [make_test_organization(), make_test_organization(org_id=uuid.uuid4(), slug="other")]

    org_service._org_repo = AsyncMock()
    org_service._org_repo.list_all.return_value = (orgs, 2)

    result = await org_service.list_organizations(user=admin)
    assert len(result) == 2
    org_service._org_repo.list_all.assert_awaited_once()
    org_service._org_repo.list_for_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_organizations_as_regular_user(org_service: OrganizationService) -> None:
    """Non-admin should only see orgs they belong to via list_for_user."""
    user = make_test_user()
    orgs = [make_test_organization()]

    org_service._org_repo = AsyncMock()
    org_service._org_repo.list_for_user.return_value = orgs

    result = await org_service.list_organizations(user=user)
    assert len(result) == 1
    org_service._org_repo.list_for_user.assert_awaited_once_with(user.id, 0, 50)
    org_service._org_repo.list_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_organization(org_service: OrganizationService) -> None:
    org = make_test_organization()
    org.name = "Updated Name"

    org_service._org_repo = AsyncMock()
    org_service._org_repo.update.return_value = org

    result = await org_service.update_organization(
        org_id=org.id,
        name="Updated Name",
    )

    assert result.name == "Updated Name"
    org_service._org_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_organization_not_found(org_service: OrganizationService) -> None:
    org_service._org_repo = AsyncMock()
    org_service._org_repo.update.return_value = None

    with pytest.raises(NotFoundError, match="Organization"):
        await org_service.update_organization(
            org_id=uuid.uuid4(),
            name="Nope",
        )


@pytest.mark.asyncio
async def test_get_organization_with_access_check_member(
    org_service: OrganizationService,
) -> None:
    """Regular user with active membership should pass the access check."""
    org = make_test_organization()
    user = make_test_user()
    membership = OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.ANALYST,
        is_active=True,
    )

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = org
    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.get_membership.return_value = membership

    result = await org_service.get_organization_with_access_check(org.id, user)
    assert result.id == org.id


@pytest.mark.asyncio
async def test_get_organization_with_access_check_admin(
    org_service: OrganizationService,
) -> None:
    """Platform admin should pass without membership check."""
    org = make_test_organization()
    admin = make_test_user(is_platform_admin=True, email="admin@example.com")

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = org
    org_service._membership_repo = AsyncMock()

    result = await org_service.get_organization_with_access_check(org.id, admin)
    assert result.id == org.id
    org_service._membership_repo.get_membership.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_organization_with_access_check_non_member(
    org_service: OrganizationService,
) -> None:
    """Non-member, non-admin should be denied."""
    org = make_test_organization()
    user = make_test_user()

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = org
    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.get_membership.return_value = None

    with pytest.raises(ForbiddenError, match="not a member"):
        await org_service.get_organization_with_access_check(org.id, user)


@pytest.mark.asyncio
async def test_verify_membership_or_admin_admin(
    org_service: OrganizationService,
) -> None:
    """Platform admin should pass verify_membership_or_admin."""
    admin = make_test_user(is_platform_admin=True, email="admin@example.com")
    org_service._membership_repo = AsyncMock()

    await org_service.verify_membership_or_admin(uuid.uuid4(), admin)
    org_service._membership_repo.get_membership.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_membership_or_admin_non_member(
    org_service: OrganizationService,
) -> None:
    """Non-member should be rejected by verify_membership_or_admin."""
    user = make_test_user()

    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.get_membership.return_value = None

    with pytest.raises(ForbiddenError, match="not a member"):
        await org_service.verify_membership_or_admin(uuid.uuid4(), user)


@pytest.mark.asyncio
async def test_add_member_duplicate_active(org_service: OrganizationService) -> None:
    """Adding a user who is already an active member should raise ConflictError."""
    org = make_test_organization()
    user = make_test_user()
    existing = OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.ANALYST,
        is_active=True,
    )

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = org
    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.get_membership.return_value = existing

    with pytest.raises(ConflictError, match="already a member"):
        await org_service.add_member(
            organization_id=org.id,
            user_id=user.id,
            role=MembershipRole.ANALYST,
            invited_by=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_add_member_reactivates_inactive(org_service: OrganizationService) -> None:
    """Adding a previously-removed member should reactivate them."""
    org = make_test_organization()
    user = make_test_user()
    existing = OrganizationMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.VIEWER,
        is_active=False,
    )

    org_service._org_repo = AsyncMock()
    org_service._org_repo.get_by_id.return_value = org
    org_service._membership_repo = AsyncMock()
    org_service._membership_repo.get_membership.return_value = existing

    result = await org_service.add_member(
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ORG_ADMIN,
        invited_by=uuid.uuid4(),
    )

    assert result.is_active is True
    assert result.role == MembershipRole.ORG_ADMIN


@pytest.mark.asyncio
async def test_add_member_requires_user_id_or_email(
    org_service: OrganizationService,
) -> None:
    """add_member should raise ValidationError if neither user_id nor email given."""
    with pytest.raises(ValidationError, match="user_id or email"):
        await org_service.add_member(
            organization_id=uuid.uuid4(),
            role=MembershipRole.ANALYST,
            invited_by=uuid.uuid4(),
        )
