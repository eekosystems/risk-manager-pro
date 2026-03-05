"""Tests for chat endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.fixture
def mock_chat_service() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient, test_user: User) -> None:
    with patch("app.api.v1.chat._get_chat_service") as mock_factory:
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
        mock_factory.return_value = mock_service
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Test question about aviation safety"},
        )
    assert response.status_code == 201
    body = response.json()
    assert "data" in body


@pytest.mark.asyncio
async def test_list_conversations(client: AsyncClient) -> None:
    with patch("app.api.v1.chat._get_chat_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.list_conversations.return_value = []
        mock_factory.return_value = mock_service
        response = await client.get("/api/v1/chat/conversations")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_get_conversation_not_found(client: AsyncClient) -> None:
    with patch("app.api.v1.chat._get_chat_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.get_conversation.return_value = None
        mock_factory.return_value = mock_service
        response = await client.get(
            "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000099"
        )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient) -> None:
    with patch("app.api.v1.chat._get_chat_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.delete_conversation.return_value = True
        mock_factory.return_value = mock_service
        response = await client.delete(
            "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000099"
        )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_conversation_not_found(client: AsyncClient) -> None:
    with patch("app.api.v1.chat._get_chat_service") as mock_factory:
        mock_service = AsyncMock()
        mock_service.delete_conversation.return_value = False
        mock_factory.return_value = mock_service
        response = await client.delete(
            "/api/v1/chat/conversations/00000000-0000-0000-0000-000000000099"
        )
    assert response.status_code == 404
