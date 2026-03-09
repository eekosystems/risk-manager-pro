"""Tests for chat service."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, FunctionType
from app.models.message import Message, MessageRole
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.chat import ChatService
from app.services.rag import SearchResult
from tests.conftest import ORGANIZATION_ID, make_test_user


@pytest.fixture
def user() -> User:
    return make_test_user()


@pytest.fixture
def chat_service(
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
) -> ChatService:
    db = AsyncMock(spec=AsyncSession)
    return ChatService(
        db=db,
        openai_client=mock_openai_client,
        rag_service=mock_rag_service,
    )


@pytest.mark.asyncio
async def test_process_message_creates_conversation(
    chat_service: ChatService,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    user: User,
) -> None:
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=ORGANIZATION_ID,
        title="Test question",
        function_type=FunctionType.GENERAL,
    )
    user_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Test question",
    )
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Test AI response.",
    )

    with patch.object(chat_service, "_repo") as mock_repo:
        mock_repo.create.return_value = conversation
        mock_repo.add_message.side_effect = [user_msg, assistant_msg]
        mock_repo.get_messages.return_value = [user_msg]

        request = ChatRequest(
            message="Test question",
            function_type=FunctionType.GENERAL,
        )
        result = await chat_service.process_message(request, user, ORGANIZATION_ID)

    assert result.conversation_id == conversation.id
    assert result.message.content == "Test AI response."
    mock_openai_client.chat_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_includes_citations(
    chat_service: ChatService,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    user: User,
) -> None:
    mock_rag_service.hybrid_search.return_value = [
        SearchResult(
            content="FAA AC 120-92B guidance",
            source="FAA AC 120-92B",
            section="Chapter 5",
            score=0.95,
            chunk_id="doc1_0",
        ),
    ]

    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=ORGANIZATION_ID,
        title="Safety question",
        function_type=FunctionType.SRA,
    )
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Based on FAA AC 120-92B...",
        citations=[
            {
                "source": "FAA AC 120-92B",
                "section": "Chapter 5",
                "content": "FAA AC 120-92B guidance",
                "score": 0.95,
                "chunk_id": "doc1_0",
            }
        ],
    )

    with patch.object(chat_service, "_repo") as mock_repo:
        mock_repo.create.return_value = conversation
        mock_repo.add_message.side_effect = [
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="test",
            ),
            assistant_msg,
        ]
        mock_repo.get_messages.return_value = []

        request = ChatRequest(
            message="Safety question",
            function_type=FunctionType.SRA,
        )
        result = await chat_service.process_message(request, user, ORGANIZATION_ID)

    assert result.message.citations is not None
    assert len(result.message.citations) == 1
    assert result.message.citations[0].source == "FAA AC 120-92B"


@pytest.mark.asyncio
async def test_process_message_handles_rag_failure(
    chat_service: ChatService,
    mock_openai_client: AsyncMock,
    mock_rag_service: AsyncMock,
    user: User,
) -> None:
    mock_rag_service.hybrid_search.side_effect = RuntimeError("Search unavailable")

    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=ORGANIZATION_ID,
        title="Test",
        function_type=FunctionType.GENERAL,
    )
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Response without context.",
    )

    with patch.object(chat_service, "_repo") as mock_repo:
        mock_repo.create.return_value = conversation
        mock_repo.add_message.side_effect = [
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="test",
            ),
            msg,
        ]
        mock_repo.get_messages.return_value = []

        request = ChatRequest(message="Test question")
        result = await chat_service.process_message(request, user, ORGANIZATION_ID)

    assert result.message.content == "Response without context."
    mock_openai_client.chat_completion.assert_awaited_once()
