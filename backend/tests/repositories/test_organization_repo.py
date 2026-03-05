"""Tests for organization repository."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User
from app.repositories.organization import MembershipRepository, OrganizationRepository
from tests.conftest import make_test_organization, make_test_user


async def _seed_org(db: AsyncSession, **kwargs: object) -> Organization:
    org = make_test_organization(**kwargs)
    db.add(org)
    await db.flush()
    return org


async def _seed_user(db: AsyncSession, **kwargs: object) -> User:
    user = make_test_user(**kwargs)
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_create_organization(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)

    org = await repo.create(
        name="Acme Aviation",
        slug="acme-aviation",
    )

    assert org.id is not None
    assert org.name == "Acme Aviation"
    assert org.slug == "acme-aviation"
    assert org.status == OrganizationStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession) -> None:
    org = await _seed_org(db_session, slug="get-by-id-test")
    repo = OrganizationRepository(db_session)

    fetched = await repo.get_by_id(org.id)
    assert fetched is not None
    assert fetched.name == org.name


@pytest.mark.asyncio
async def test_get_by_slug(db_session: AsyncSession) -> None:
    org = await _seed_org(db_session, slug="slug-test-unique")
    repo = OrganizationRepository(db_session)

    fetched = await repo.get_by_slug("slug-test-unique")
    assert fetched is not None
    assert fetched.id == org.id


@pytest.mark.asyncio
async def test_list_all(db_session: AsyncSession) -> None:
    await _seed_org(db_session, slug="list-test-1", org_id=uuid.uuid4())
    await _seed_org(db_session, slug="list-test-2", org_id=uuid.uuid4())
    repo = OrganizationRepository(db_session)

    orgs = await repo.list_all()
    assert len(orgs) >= 2


@pytest.mark.asyncio
async def test_add_member(db_session: AsyncSession) -> None:
    org = await _seed_org(db_session, slug="member-test")
    user = await _seed_user(db_session, email="member@test.com")
    repo = MembershipRepository(db_session)

    membership = await repo.add_member(
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.ANALYST,
    )

    assert membership.user_id == user.id
    assert membership.organization_id == org.id
    assert membership.role == MembershipRole.ANALYST
    assert membership.is_active is True


@pytest.mark.asyncio
async def test_get_membership(db_session: AsyncSession) -> None:
    org = await _seed_org(db_session, slug="get-member-test")
    user = await _seed_user(db_session, email="getmember@test.com")
    repo = MembershipRepository(db_session)

    await repo.add_member(
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.VIEWER,
    )

    membership = await repo.get_membership(user.id, org.id)
    assert membership is not None
    assert membership.role == MembershipRole.VIEWER


@pytest.mark.asyncio
async def test_list_members(db_session: AsyncSession) -> None:
    org = await _seed_org(db_session, slug="list-members-test")
    user1 = await _seed_user(db_session, email="list1@test.com")
    user2 = await _seed_user(db_session, email="list2@test.com")
    repo = MembershipRepository(db_session)

    await repo.add_member(user_id=user1.id, organization_id=org.id, role=MembershipRole.ANALYST)
    await repo.add_member(user_id=user2.id, organization_id=org.id, role=MembershipRole.VIEWER)

    members = await repo.list_members(org.id)
    assert len(members) == 2


@pytest.mark.asyncio
async def test_update_role(db_session: AsyncSession) -> None:
    org = await _seed_org(db_session, slug="update-role-test")
    user = await _seed_user(db_session, email="updaterole@test.com")
    repo = MembershipRepository(db_session)

    await repo.add_member(user_id=user.id, organization_id=org.id, role=MembershipRole.VIEWER)

    updated = await repo.update_role(user.id, org.id, MembershipRole.ORG_ADMIN)
    assert updated is not None
    assert updated.role == MembershipRole.ORG_ADMIN


@pytest.mark.asyncio
async def test_remove_member(db_session: AsyncSession) -> None:
    org = await _seed_org(db_session, slug="remove-member-test")
    user = await _seed_user(db_session, email="removemember@test.com")
    repo = MembershipRepository(db_session)

    await repo.add_member(user_id=user.id, organization_id=org.id, role=MembershipRole.ANALYST)

    result = await repo.remove_member(user.id, org.id)
    assert result is True

    membership = await repo.get_membership(user.id, org.id)
    assert membership is None or membership.is_active is False
