"""Tests for correlation ID middleware."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_generates_correlation_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    correlation_id = response.headers.get("X-Correlation-ID")
    assert correlation_id is not None
    # Should be a valid UUID
    uuid.UUID(correlation_id)


@pytest.mark.asyncio
async def test_uses_provided_correlation_id(client: AsyncClient) -> None:
    custom_id = str(uuid.uuid4())
    response = await client.get(
        "/api/v1/health",
        headers={"X-Correlation-ID": custom_id},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_id
