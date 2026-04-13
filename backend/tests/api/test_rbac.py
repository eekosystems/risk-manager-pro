"""RBAC enforcement matrix across role x endpoint.

Requires RMP_ENFORCE_RBAC=true (set by the fixture via monkeypatch) so we can
verify the production-mode behavior regardless of environment default.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
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
from tests.conftest import make_test_membership, make_test_user


@pytest.fixture(autouse=True)
def _enforce_rbac(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "enforce_rbac", True)


async def _build_app(
    db_session: AsyncSession,
    user: User,
    organization: Organization,
    role: MembershipRole,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> FastAPI:
    db_session.add(organization)
    await db_session.flush()
    db_session.add(user)
    await db_session.flush()
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


@pytest.mark.asyncio
async def test_viewer_cannot_create_risk(
    db_session: AsyncSession,
    test_organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    viewer = make_test_user(email="viewer@example.com")
    app = await _build_app(
        db_session,
        viewer,
        test_organization,
        MembershipRole.VIEWER,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/risks",
            json={
                "title": "Should be blocked",
                "description": "desc",
                "hazard": "hazard",
                "severity": 3,
                "likelihood": "C",
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_can_list_risks(
    db_session: AsyncSession,
    test_organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    viewer = make_test_user(email="viewer2@example.com")
    app = await _build_app(
        db_session,
        viewer,
        test_organization,
        MembershipRole.VIEWER,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/risks")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_analyst_can_create_risk(
    db_session: AsyncSession,
    test_organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    analyst = make_test_user(email="analyst@example.com")
    app = await _build_app(
        db_session,
        analyst,
        test_organization,
        MembershipRole.ANALYST,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/risks",
            json={
                "title": "Should be allowed",
                "description": "desc",
                "hazard": "hazard",
                "severity": 3,
                "likelihood": "C",
            },
        )
    assert response.status_code == 201
