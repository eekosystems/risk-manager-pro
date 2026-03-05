"""Tests for user endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    profile = body["data"]
    assert "id" in profile
    assert "email" in profile
    assert "display_name" in profile
    assert "is_platform_admin" in profile
    assert "is_active" in profile


@pytest.mark.asyncio
async def test_get_current_user_profile_wrapped_in_data_response(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/users/me")
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "request_id" in body["meta"]
