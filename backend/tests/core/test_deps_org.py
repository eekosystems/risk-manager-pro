"""Tests for organization-related dependencies."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    LAST_LOGIN_THROTTLE,
    get_current_organization,
    get_current_user,
    require_org_role,
    require_platform_admin,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User
from tests.conftest import ORGANIZATION_ID, make_test_organization, make_test_user


@pytest.mark.asyncio
async def test_require_platform_admin_passes_for_admin() -> None:
    user = make_test_user(is_platform_admin=True)
    # Call the dependency directly with the user
    result = await require_platform_admin(current_user=user)
    assert result == user


@pytest.mark.asyncio
async def test_require_platform_admin_rejects_non_admin() -> None:
    user = make_test_user(is_platform_admin=False)

    with pytest.raises(ForbiddenError, match="Platform admin"):
        await require_platform_admin(current_user=user)


@pytest.mark.asyncio
async def test_require_org_role_allows_platform_admin(db_session: AsyncSession) -> None:
    user = make_test_user(is_platform_admin=True)
    org = make_test_organization()

    checker = require_org_role(MembershipRole.ORG_ADMIN)
    # Platform admins bypass role checks
    result = await checker(current_user=user, organization=org, db=db_session)
    assert result == user


@pytest.mark.asyncio
async def test_require_org_role_allows_matching_role(db_session: AsyncSession) -> None:
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user()
    db_session.add(user)
    await db_session.flush()

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.ANALYST,
        is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()

    checker = require_org_role(MembershipRole.ANALYST, MembershipRole.ORG_ADMIN)
    result = await checker(current_user=user, organization=org, db=db_session)
    assert result == user


@pytest.mark.asyncio
async def test_require_org_role_rejects_wrong_role(db_session: AsyncSession) -> None:
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user()
    db_session.add(user)
    await db_session.flush()

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.VIEWER,
        is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()

    checker = require_org_role(MembershipRole.ORG_ADMIN)
    with pytest.raises(ForbiddenError):
        await checker(current_user=user, organization=org, db=db_session)


@pytest.mark.asyncio
async def test_require_org_role_rejects_non_member(db_session: AsyncSession) -> None:
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user()
    db_session.add(user)
    await db_session.flush()

    # No membership created
    checker = require_org_role(MembershipRole.ANALYST)
    with pytest.raises(ForbiddenError):
        await checker(current_user=user, organization=org, db=db_session)


# --- Inactive User Tests ---


@pytest.fixture
def mock_request() -> MagicMock:
    """Minimal mock request for deps that need it."""
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers.get.return_value = "TestAgent/1.0"
    request.state.correlation_id = str(uuid.uuid4())
    return request


@pytest.fixture
def mock_token() -> MagicMock:
    """Mock TokenPayload."""
    token = MagicMock()
    token.oid = str(uuid.uuid4())
    token.preferred_username = "test@example.com"
    token.name = "Test User"
    token.tid = str(uuid.uuid4())
    return token


@pytest.mark.asyncio
async def test_inactive_user_rejected(
    db_session: AsyncSession, mock_request: MagicMock, mock_token: MagicMock
) -> None:
    """A deactivated user should be rejected with ForbiddenError."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user(is_active=False)
    user.entra_id = mock_token.oid
    db_session.add(user)
    await db_session.flush()

    with pytest.raises(ForbiddenError, match="deactivated"):
        await get_current_user(request=mock_request, token=mock_token, db=db_session)


@pytest.mark.asyncio
async def test_active_user_accepted(
    db_session: AsyncSession, mock_request: MagicMock, mock_token: MagicMock
) -> None:
    """An active user should pass get_current_user."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user(is_active=True)
    user.entra_id = mock_token.oid
    db_session.add(user)
    await db_session.flush()

    result = await get_current_user(
        request=mock_request, token=mock_token, db=db_session
    )
    assert result.id == user.id
    assert result.is_active is True


# --- Last Login Throttling Tests ---


@pytest.mark.asyncio
async def test_last_login_updated_when_stale(
    db_session: AsyncSession, mock_request: MagicMock, mock_token: MagicMock
) -> None:
    """last_login should update when more than LAST_LOGIN_THROTTLE has elapsed."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    user = make_test_user()
    user.entra_id = mock_token.oid
    user.last_login = stale_time
    db_session.add(user)
    await db_session.flush()

    result = await get_current_user(
        request=mock_request, token=mock_token, db=db_session
    )

    assert result.last_login is not None
    assert result.last_login > stale_time


@pytest.mark.asyncio
async def test_last_login_not_updated_when_recent(
    db_session: AsyncSession, mock_request: MagicMock, mock_token: MagicMock
) -> None:
    """last_login should NOT update when within LAST_LOGIN_THROTTLE window."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    user = make_test_user()
    user.entra_id = mock_token.oid
    user.last_login = recent_time
    db_session.add(user)
    await db_session.flush()

    result = await get_current_user(
        request=mock_request, token=mock_token, db=db_session
    )

    assert result.last_login == recent_time


@pytest.mark.asyncio
async def test_last_login_set_when_none(
    db_session: AsyncSession, mock_request: MagicMock, mock_token: MagicMock
) -> None:
    """last_login should be set when it's None."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user()
    user.entra_id = mock_token.oid
    user.last_login = None
    db_session.add(user)
    await db_session.flush()

    result = await get_current_user(
        request=mock_request, token=mock_token, db=db_session
    )

    assert result.last_login is not None


# --- Suspended Organization Tests ---


@pytest.mark.asyncio
async def test_suspended_org_rejected(db_session: AsyncSession) -> None:
    """Requesting a suspended organization should raise NotFoundError."""
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name="Suspended Corp",
        slug="suspended-corp",
        status=OrganizationStatus.SUSPENDED,
        is_platform=False,
    )
    db_session.add(org)
    await db_session.flush()

    user = make_test_user(is_platform_admin=True)

    with pytest.raises(NotFoundError):
        await get_current_organization(
            current_user=user, db=db_session, x_organization_id=str(org_id)
        )


@pytest.mark.asyncio
async def test_active_org_accepted(db_session: AsyncSession) -> None:
    """Requesting an active org as a platform admin should succeed."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user(is_platform_admin=True)

    result = await get_current_organization(
        current_user=user, db=db_session, x_organization_id=str(org.id)
    )
    assert result.id == org.id
    assert result.status == OrganizationStatus.ACTIVE


@pytest.mark.asyncio
async def test_org_access_requires_membership(db_session: AsyncSession) -> None:
    """Non-admin user without membership should be denied org access."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user()
    db_session.add(user)
    await db_session.flush()

    # No membership for this user
    with pytest.raises(ForbiddenError, match="not a member"):
        await get_current_organization(
            current_user=user, db=db_session, x_organization_id=str(org.id)
        )


@pytest.mark.asyncio
async def test_org_access_with_membership(db_session: AsyncSession) -> None:
    """Non-admin user with active membership should pass."""
    org = make_test_organization()
    db_session.add(org)
    await db_session.flush()

    user = make_test_user()
    db_session.add(user)
    await db_session.flush()

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.ANALYST,
        is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()

    result = await get_current_organization(
        current_user=user, db=db_session, x_organization_id=str(org.id)
    )
    assert result.id == org.id
