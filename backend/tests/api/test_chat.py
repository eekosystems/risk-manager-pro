"""Tests for chat endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.v1.chat import _get_chat_service
from app.models.user import User


@pytest.fixture
def mock_chat_service() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_send_message(test_app: FastAPI, client: AsyncClient, test_user: User) -> None:
    mock_service = AsyncMock()
    mock_service.process_message.return_value = AsyncMock(
        conversation_id=test_user.id,
        message=AsyncMock(
            id=test_user.id,
            role="assistant",
            content="Test response",
            citations=None,
            created_at="2024-01-01T00:00:00Z",
        ),
        title="Test conversation",
    )
    test_app.dependency_overrides[_get_chat_service] = lambda: mock_service
    response = await client.post(
        "/api/v1/chat",
        json={"message": "Test question about aviation safety"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "data" in body


@pytest.mark.asyncio
async def test_list_conversations(test_app: FastAPI, client: AsyncClient) -> None:
    mock_service = AsyncMock()
    mock_service.list_conversations.return_value = []
    test_app.dependency_overrides[_get_chat_service] = lambda: mock_service
    response = await client.get("/api/v1/chat/conversations")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_get_conversation_not_found(test_app: FastAPI, client: AsyncClient) -> None:
    mock_service = AsyncMock()
    mock_service.get_conversation.return_value = None
    test_app.dependency_overrides[_get_chat_service] = lambda: mock_service
    response = await client.get("/api/v1/chat/conversations/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_conversation(test_app: FastAPI, client: AsyncClient) -> None:
    mock_service = AsyncMock()
    mock_service.delete_conversation.return_value = True
    test_app.dependency_overrides[_get_chat_service] = lambda: mock_service
    response = await client.delete(
        "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000099"
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_conversation_not_found(test_app: FastAPI, client: AsyncClient) -> None:
    mock_service = AsyncMock()
    mock_service.delete_conversation.return_value = False
    test_app.dependency_overrides[_get_chat_service] = lambda: mock_service
    response = await client.delete(
        "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000099"
    )
    assert response.status_code == 404
