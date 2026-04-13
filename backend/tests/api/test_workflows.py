"""Integration tests for the PHL/SRA workflow API."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
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
from app.models.risk import RiskEntry
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStatus
from tests.conftest import make_test_membership, make_test_user


async def _build_app(
    db_session: AsyncSession,
    admin_user: User,
    organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> FastAPI:
    db_session.add(organization)
    await db_session.flush()
    db_session.add(admin_user)
    await db_session.flush()
    db_session.add(
        make_test_membership(admin_user.id, organization.id, role=MembershipRole.ORG_ADMIN)
    )
    await db_session.flush()

    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    from app.core.database import get_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_current_organization] = lambda: organization
    app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger
    app.dependency_overrides[get_openai_client] = lambda: mock_openai_client
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
    app.dependency_overrides[get_search_indexer] = lambda: mock_search_indexer
    return app


@pytest.mark.asyncio
async def test_sra_workflow_draft_submit_approve_creates_risk(
    db_session: AsyncSession,
    test_organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    admin = make_test_user(email="admin-wf@example.com")
    app = await _build_app(
        db_session,
        admin,
        test_organization,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post(
            "/api/v1/workflows",
            json={
                "type": "sra",
                "title": "Runway excursion SRA",
                "data": {
                    "title": "Runway excursion risk",
                    "description": "Potential excursion during wet conditions",
                    "hazard": "Reduced braking performance on wet runway",
                    "severity": 4,
                    "likelihood": "C",
                },
            },
        )
        assert create_resp.status_code == 201
        workflow_id = create_resp.json()["data"]["id"]

        patch_resp = await client.patch(
            f"/api/v1/workflows/{workflow_id}",
            json={"data": {"notes": "Additional context"}},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["data"]["notes"] == "Additional context"

        submit_resp = await client.post(f"/api/v1/workflows/{workflow_id}/submit")
        assert submit_resp.status_code == 200
        assert submit_resp.json()["data"]["status"] == "submitted"

        approve_resp = await client.post(
            f"/api/v1/workflows/{workflow_id}/approve",
            json={"approve": True},
        )
        assert approve_resp.status_code == 200
        body = approve_resp.json()["data"]
        assert body["status"] == "approved"
        assert body["risk_entry_id"] is not None

    wf_result = await db_session.execute(select(Workflow))
    workflow = wf_result.scalar_one()
    assert workflow.status == WorkflowStatus.APPROVED

    risk_result = await db_session.execute(
        select(RiskEntry).where(RiskEntry.id == workflow.risk_entry_id)
    )
    risk = risk_result.scalar_one()
    assert risk.severity == 4
    assert risk.likelihood == "C"


@pytest.mark.asyncio
async def test_cannot_edit_submitted_workflow(
    db_session: AsyncSession,
    test_organization: Organization,
    mock_audit_logger: AsyncMock,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    mock_storage_service: AsyncMock,
    mock_search_indexer: AsyncMock,
) -> None:
    admin = make_test_user(email="admin-wf2@example.com")
    app = await _build_app(
        db_session,
        admin,
        test_organization,
        mock_audit_logger,
        mock_openai_client,
        mock_rag_service,
        mock_storage_service,
        mock_search_indexer,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/api/v1/workflows", json={"type": "phl", "title": "PHL"})
        workflow_id = create_resp.json()["data"]["id"]
        await client.post(f"/api/v1/workflows/{workflow_id}/submit")

        patch_resp = await client.patch(
            f"/api/v1/workflows/{workflow_id}",
            json={"title": "Attempted change"},
        )
    assert patch_resp.status_code == 409
