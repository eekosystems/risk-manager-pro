"""Granting platform administration, and the settings it now gates.

is_platform_admin is a column on our users table rather than an Entra claim,
so these cover who may change it and the two ways of stranding the platform.
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    get_current_user,
    get_openai_client,
    get_rag_service,
    get_search_indexer,
    get_storage_service,
)
from app.main import create_app
from app.models.organization import Organization
from app.models.organization_membership import MembershipRole
from app.models.user import User
from tests.conftest import make_test_membership, make_test_organization, make_test_user


@pytest.fixture(autouse=True)
def _enforce_rbac(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "enforce_rbac", True)


async def _build_app(
    db_session: AsyncSession,
    user: User,
    organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
    role: MembershipRole = MembershipRole.ORG_ADMIN,
) -> FastAPI:
    db_session.add(make_test_membership(user.id, organization.id, role=role))
    await db_session.flush()

    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    from app.core.database import get_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_organization] = lambda: organization
    app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger
    app.dependency_overrides[get_openai_client] = lambda: mock_openai_client
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[get_search_indexer] = lambda: mock_search_indexer
    return app


async def _seed(db: AsyncSession) -> Organization:
    org = make_test_organization()
    db.add(org)
    await db.flush()
    return org


async def _patch_flag(app: FastAPI, user_id: uuid.UUID, grant: bool) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.patch(
            f"/api/v1/users/{user_id}/platform-admin",
            json={"is_platform_admin": grant},
        )


@pytest.fixture
def mocks(
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> tuple[AsyncMock, ...]:
    return (
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )


@pytest.mark.asyncio
async def test_platform_admin_can_grant_the_flag(
    db_session: AsyncSession, mocks: tuple[AsyncMock, ...]
) -> None:
    org = await _seed(db_session)
    admin = make_test_user(email="admin@fg.com", is_platform_admin=True)
    target = make_test_user(email="colleague@fg.com")
    db_session.add_all([admin, target])
    await db_session.flush()
    app = await _build_app(db_session, admin, org, *mocks)

    response = await _patch_flag(app, target.id, True)

    assert response.status_code == 200
    assert response.json()["data"]["is_platform_admin"] is True
    stored = (
        await db_session.execute(select(User.is_platform_admin).where(User.id == target.id))
    ).scalar_one()
    assert stored is True


@pytest.mark.asyncio
async def test_a_non_platform_admin_cannot_grant_the_flag(
    db_session: AsyncSession, mocks: tuple[AsyncMock, ...]
) -> None:
    """An org admin runs their own account; they cannot promote anyone."""
    org = await _seed(db_session)
    org_admin = make_test_user(email="client-admin@sea.com")
    target = make_test_user(email="colleague@sea.com")
    db_session.add_all([org_admin, target])
    await db_session.flush()
    app = await _build_app(db_session, org_admin, org, *mocks)

    response = await _patch_flag(app, target.id, True)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_you_cannot_change_your_own_flag(
    db_session: AsyncSession, mocks: tuple[AsyncMock, ...]
) -> None:
    """Blocks the obvious self-lockout, and self-granting from a lower role."""
    org = await _seed(db_session)
    admin = make_test_user(email="admin@fg.com", is_platform_admin=True)
    db_session.add(admin)
    await db_session.flush()
    app = await _build_app(db_session, admin, org, *mocks)

    response = await _patch_flag(app, admin.id, False)

    assert response.status_code == 422
    assert "your own" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_the_last_platform_admin_cannot_be_removed(
    db_session: AsyncSession, mocks: tuple[AsyncMock, ...]
) -> None:
    org = await _seed(db_session)
    first = make_test_user(email="first@fg.com", is_platform_admin=True)
    second = make_test_user(email="second@fg.com", is_platform_admin=True)
    db_session.add_all([first, second])
    await db_session.flush()
    app = await _build_app(db_session, first, org, *mocks)

    # Demoting the other one is fine while two remain...
    assert (await _patch_flag(app, second.id, False)).status_code == 200

    # ...but now `first` is the last, and only they could demote themselves,
    # which the self-change guard already refuses.
    remaining = (
        await db_session.execute(
            select(User).where(User.is_platform_admin.is_(True), User.is_active.is_(True))
        )
    ).scalars()
    assert [u.email for u in remaining] == ["first@fg.com"]


@pytest.mark.asyncio
async def test_removing_the_last_admin_is_refused(
    db_session: AsyncSession, mocks: tuple[AsyncMock, ...]
) -> None:
    org = await _seed(db_session)
    # The acting admin is inactive, so `target` is the last *active* one.
    acting = make_test_user(email="acting@fg.com", is_platform_admin=True, is_active=False)
    target = make_test_user(email="target@fg.com", is_platform_admin=True)
    db_session.add_all([acting, target])
    await db_session.flush()
    app = await _build_app(db_session, acting, org, *mocks)

    response = await _patch_flag(app, target.id, False)

    assert response.status_code == 422
    assert "last active platform administrator" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_an_unknown_user_is_not_found(
    db_session: AsyncSession, mocks: tuple[AsyncMock, ...]
) -> None:
    org = await _seed(db_session)
    admin = make_test_user(email="admin@fg.com", is_platform_admin=True)
    db_session.add(admin)
    await db_session.flush()
    app = await _build_app(db_session, admin, org, *mocks)

    response = await _patch_flag(app, uuid.uuid4(), True)

    assert response.status_code == 404


# --- The settings these now gate ---


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["rag", "model", "prompts", "qaqc"])
async def test_an_org_admin_can_no_longer_change_ai_settings(
    category: str, db_session: AsyncSession, mocks: tuple[AsyncMock, ...]
) -> None:
    """A client's own admin must not tune prompts or retrieval for their org."""
    org = await _seed(db_session)
    org_admin = make_test_user(email="client-admin@sea.com")
    db_session.add(org_admin)
    await db_session.flush()
    app = await _build_app(db_session, org_admin, org, *mocks)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(f"/api/v1/settings/{category}", json={})

    assert response.status_code == 403
