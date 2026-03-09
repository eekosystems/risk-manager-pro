"""Tests for organization endpoints."""

import pytest
from httpx import AsyncClient

from tests.conftest import ORGANIZATION_ID


@pytest.mark.asyncio
async def test_list_organizations(client: AsyncClient) -> None:
    response = await client.get("/api/v1/organizations")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body


@pytest.mark.asyncio
async def test_get_organization(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/organizations/{ORGANIZATION_ID}")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body


@pytest.mark.asyncio
async def test_create_organization_requires_platform_admin(
    client: AsyncClient,
) -> None:
    """Non-platform-admin users should be denied org creation."""
    response = await client.post(
        "/api/v1/organizations",
        json={"name": "New Client Org", "slug": "new-client"},
    )
    # Default test_user is NOT a platform admin, so this should be 403
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_organization_members(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/organizations/{ORGANIZATION_ID}/members")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body


# --- Admin Happy Path Tests ---


@pytest.mark.asyncio
async def test_admin_create_organization(admin_client: AsyncClient) -> None:
    """Platform admin should be able to create an organization."""
    response = await admin_client.post(
        "/api/v1/organizations",
        json={"name": "New Aviation Corp", "slug": "new-aviation-corp"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["data"]["name"] == "New Aviation Corp"
    assert body["data"]["slug"] == "new-aviation-corp"


@pytest.mark.asyncio
async def test_admin_update_organization(admin_client: AsyncClient) -> None:
    """Platform admin should be able to update an organization."""
    response = await admin_client.patch(
        f"/api/v1/organizations/{ORGANIZATION_ID}",
        json={"name": "Updated Test Org"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["name"] == "Updated Test Org"


@pytest.mark.asyncio
async def test_admin_list_members(admin_client: AsyncClient) -> None:
    """Platform admin should be able to list members of any organization."""
    response = await admin_client.get(f"/api/v1/organizations/{ORGANIZATION_ID}/members")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_admin_get_organization(admin_client: AsyncClient) -> None:
    """Platform admin should be able to read any organization."""
    response = await admin_client.get(f"/api/v1/organizations/{ORGANIZATION_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == str(ORGANIZATION_ID)
