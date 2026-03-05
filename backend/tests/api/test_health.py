"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body


@pytest.mark.asyncio
async def test_readiness_checks_database(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ready", "degraded")
    assert "checks" in body
    assert "database" in body["checks"]
