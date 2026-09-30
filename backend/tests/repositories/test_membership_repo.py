"""Tests for membership repository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization_membership import MembershipRole
from app.repositories.membership import MembershipRepository
from app.services.organization import _membership_to_response
from tests.conftest import make_test_organization, make_test_user


@pytest.mark.asyncio
async def test_update_role_loads_user_for_response(db_session: AsyncSession) -> None:
    org = make_test_organization()
    db_session.add(org)
    member = make_test_user()
    db_session.add(member)
    await db_session.flush()
    repo = MembershipRepository(db_session)
    await repo.add_member(member.id, org.id, role=MembershipRole.VIEWER)
    # Forget every loaded object, as a request that never touched the member
    # would have: the response must not depend on a lazy load of the user.
    db_session.expunge_all()

    membership = await repo.update_role(member.id, org.id, MembershipRole.ORG_ADMIN)

    assert membership is not None
    response = _membership_to_response(membership)
    assert response.role == MembershipRole.ORG_ADMIN
    assert response.email == member.email
    assert response.display_name == member.display_name


@pytest.mark.asyncio
async def test_add_member_loads_user_for_response(db_session: AsyncSession) -> None:
    org = make_test_organization()
    db_session.add(org)
    member = make_test_user()
    db_session.add(member)
    await db_session.flush()
    member_id, member_email = member.id, member.email
    db_session.expunge_all()
    repo = MembershipRepository(db_session)

    membership = await repo.add_member(member_id, org.id, role=MembershipRole.ANALYST)

    response = _membership_to_response(membership)
    assert response.email == member_email
    assert response.role == MembershipRole.ANALYST
