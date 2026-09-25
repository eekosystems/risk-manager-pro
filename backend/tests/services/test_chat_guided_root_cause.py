"""Routing, prompt and interception guarantees for guided root-cause mode.

System Analysis offers two ways to run its 5 Whys stage: automated (the
model asks and answers every "why" in one pass) and guided (the model asks
one "why" per turn and the user answers). The guarantees here keep the
guided flow pinned across the user's short replies, release it when the
report is requested, and make sure the choice is offered exactly once.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, FunctionType
from app.models.message import Message, MessageRole
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.chat import (
    _ROOT_CAUSE_MODE_CHOICE,
    SYSTEM_PROMPTS,
    ChatService,
    _build_default_followups_block,
    _resolve_prompt,
)
from app.services.prompts import GUIDED_ROOT_CAUSE_ADDENDUM, SYSTEM_ANALYSIS_PROMPT
from app.services.routing import classify_function
from app.services.settings import DEFAULT_PROMPTS
from tests.conftest import ORGANIZATION_ID, make_test_user


def _conversation(function_type: FunctionType) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        user_id=make_test_user().id,
        organization_id=ORGANIZATION_ID,
        title="Runway incursion",
        function_type=function_type,
    )


def _message(conversation_id: uuid.UUID, role: MessageRole, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=datetime.now(),
    )


@pytest.fixture
def user() -> User:
    return make_test_user()


@pytest.fixture
def chat_service(mock_openai_client: AsyncMock, mock_rag_service: AsyncMock) -> ChatService:
    return ChatService(
        db=AsyncMock(spec=AsyncSession),
        openai_client=mock_openai_client,
        rag_service=mock_rag_service,
    )


# --- Routing -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_typed_answer_stays_in_guided_mode(chat_service: ChatService) -> None:
    """A one-line answer to a "why" must reach the guided prompt, not the classifier."""
    request = ChatRequest(
        message="Because the NOTAM was issued after the crew briefing.",
        function_type=FunctionType.GENERAL,
    )
    with patch("app.services.chat.classify_function", AsyncMock()) as classifier:
        routed = await chat_service._route_function_type(
            request, _conversation(FunctionType.SYSTEM_GUIDED)
        )
    assert routed == FunctionType.SYSTEM_GUIDED
    classifier.assert_not_awaited()


@pytest.mark.asyncio
async def test_locked_general_chip_stays_in_guided_mode(chat_service: ChatService) -> None:
    request = ChatRequest(
        message="Confirm the output above is accurate before we proceed.",
        function_type=FunctionType.GENERAL,
        routing_locked=True,
    )
    routed = await chat_service._route_function_type(
        request, _conversation(FunctionType.SYSTEM_GUIDED)
    )
    assert routed == FunctionType.SYSTEM_GUIDED


@pytest.mark.asyncio
async def test_finish_report_chip_hops_to_system_analysis(chat_service: ChatService) -> None:
    request = ChatRequest(
        message="Produce the full system analysis report using the 5 Whys chain.",
        function_type=FunctionType.SYSTEM_ANALYSIS,
        routing_locked=True,
    )
    routed = await chat_service._route_function_type(
        request, _conversation(FunctionType.SYSTEM_GUIDED)
    )
    assert routed == FunctionType.SYSTEM_ANALYSIS


@pytest.mark.asyncio
async def test_walk_me_through_phrasing_routes_straight_to_guided(
    mock_openai_client: AsyncMock,
) -> None:
    routed = await classify_function(
        "Walk me through the 5 Whys for yesterday's runway incursion",
        mock_openai_client,
        fallback=FunctionType.GENERAL,
    )
    assert routed == FunctionType.SYSTEM_GUIDED
    mock_openai_client.chat_completion.assert_not_awaited()


# --- Pinning -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_guided_chip_pins_conversation(chat_service: ChatService) -> None:
    conversation = _conversation(FunctionType.SYSTEM_ANALYSIS)
    mock_repo = AsyncMock()
    with patch.object(chat_service, "_repo", mock_repo):
        await chat_service._pin_sticky_function(
            conversation, FunctionType.SYSTEM_GUIDED, ORGANIZATION_ID
        )
    mock_repo.set_function_type.assert_awaited_once_with(
        conversation_id=conversation.id,
        organization_id=ORGANIZATION_ID,
        function_type=FunctionType.SYSTEM_GUIDED,
    )
    assert conversation.function_type == FunctionType.SYSTEM_GUIDED


@pytest.mark.asyncio
async def test_finishing_the_report_releases_the_guided_pin(chat_service: ChatService) -> None:
    conversation = _conversation(FunctionType.SYSTEM_GUIDED)
    mock_repo = AsyncMock()
    with patch.object(chat_service, "_repo", mock_repo):
        await chat_service._pin_sticky_function(
            conversation, FunctionType.SYSTEM_ANALYSIS, ORGANIZATION_ID
        )
    mock_repo.set_function_type.assert_awaited_once_with(
        conversation_id=conversation.id,
        organization_id=ORGANIZATION_ID,
        function_type=FunctionType.SYSTEM_ANALYSIS,
    )
    assert conversation.function_type == FunctionType.SYSTEM_ANALYSIS


@pytest.mark.asyncio
async def test_register_pin_is_kept_on_hop_out(chat_service: ChatService) -> None:
    """Risk Register keeps its pin until the chat ends; only guided mode releases."""
    conversation = _conversation(FunctionType.RISK_REGISTER)
    mock_repo = AsyncMock()
    with patch.object(chat_service, "_repo", mock_repo):
        await chat_service._pin_sticky_function(conversation, FunctionType.SRA, ORGANIZATION_ID)
    mock_repo.set_function_type.assert_not_awaited()
    assert conversation.function_type == FunctionType.RISK_REGISTER


# --- Mode choice -------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_system_analysis_turn_offers_the_mode_choice(
    chat_service: ChatService, mock_openai_client: AsyncMock, user: User
) -> None:
    conversation = _conversation(FunctionType.SYSTEM_ANALYSIS)
    user_msg = _message(conversation.id, MessageRole.USER, "Runway incursion at KSFO")
    choice_msg = _message(conversation.id, MessageRole.ASSISTANT, _ROOT_CAUSE_MODE_CHOICE)

    mock_repo = AsyncMock()
    mock_repo.create.return_value = conversation
    mock_repo.add_message.side_effect = [user_msg, choice_msg]
    mock_repo.has_assistant_message_for.return_value = False

    with (
        patch.object(chat_service, "_repo", mock_repo),
        patch(
            "app.services.chat.classify_function",
            AsyncMock(return_value=FunctionType.SYSTEM_ANALYSIS),
        ),
    ):
        request = ChatRequest(
            message="Runway incursion at KSFO", function_type=FunctionType.SYSTEM_ANALYSIS
        )
        result = await chat_service.process_message(request, user, ORGANIZATION_ID)

    assert result.routed_function_type == FunctionType.SYSTEM_ANALYSIS
    assert "system_guided | Guide Me Through The 5 Whys" in result.message.content
    assert "| system | Run The Automated Analysis" in result.message.content
    mock_openai_client.chat_completion.assert_not_awaited()
    saved_metadata = mock_repo.add_message.await_args_list[1].kwargs["metadata"]
    assert saved_metadata["root_cause_mode_choice"] is True
    assert saved_metadata["function_type"] == FunctionType.SYSTEM_ANALYSIS.value


@pytest.mark.asyncio
async def test_streamed_first_turn_offers_the_mode_choice(
    chat_service: ChatService, mock_openai_client: AsyncMock, user: User
) -> None:
    conversation = _conversation(FunctionType.SYSTEM_ANALYSIS)
    user_msg = _message(conversation.id, MessageRole.USER, "Runway incursion at KSFO")
    choice_msg = _message(conversation.id, MessageRole.ASSISTANT, _ROOT_CAUSE_MODE_CHOICE)

    mock_repo = AsyncMock()
    mock_repo.create.return_value = conversation
    mock_repo.add_message.side_effect = [user_msg, choice_msg]
    mock_repo.has_assistant_message_for.return_value = False

    with (
        patch.object(chat_service, "_repo", mock_repo),
        patch(
            "app.services.chat.classify_function",
            AsyncMock(return_value=FunctionType.SYSTEM_ANALYSIS),
        ),
    ):
        request = ChatRequest(
            message="Runway incursion at KSFO", function_type=FunctionType.SYSTEM_ANALYSIS
        )
        events = [
            event
            async for event in chat_service.process_message_stream(request, user, ORGANIZATION_ID)
        ]

    assert [e["event"] for e in events] == ["metadata", "delta", "done"]
    assert events[1]["content"] == _ROOT_CAUSE_MODE_CHOICE
    assert events[2]["message_id"] == str(choice_msg.id)
    mock_openai_client.chat_completion_stream.assert_not_called()


@pytest.mark.asyncio
async def test_chip_click_never_reoffers_the_choice(chat_service: ChatService) -> None:
    request = ChatRequest(
        message="Run the full automated system analysis and root-cause report now.",
        function_type=FunctionType.SYSTEM_ANALYSIS,
        routing_locked=True,
    )
    mock_repo = AsyncMock()
    with patch.object(chat_service, "_repo", mock_repo):
        offer = await chat_service._should_offer_root_cause_mode_choice(
            request,
            _conversation(FunctionType.SYSTEM_ANALYSIS),
            FunctionType.SYSTEM_ANALYSIS,
            ORGANIZATION_ID,
        )
    assert offer is False
    mock_repo.has_assistant_message_for.assert_not_awaited()


@pytest.mark.asyncio
async def test_choice_is_not_reoffered_after_an_analysis_reply(
    chat_service: ChatService,
) -> None:
    request = ChatRequest(
        message="Expand on corrective action 2", function_type=FunctionType.SYSTEM_ANALYSIS
    )
    mock_repo = AsyncMock()
    mock_repo.has_assistant_message_for.return_value = True
    with patch.object(chat_service, "_repo", mock_repo):
        offer = await chat_service._should_offer_root_cause_mode_choice(
            request,
            _conversation(FunctionType.SYSTEM_ANALYSIS),
            FunctionType.SYSTEM_ANALYSIS,
            ORGANIZATION_ID,
        )
    assert offer is False


@pytest.mark.asyncio
async def test_choice_is_only_for_system_analysis(chat_service: ChatService) -> None:
    request = ChatRequest(message="Assess this hazard", function_type=FunctionType.SRA)
    mock_repo = AsyncMock()
    mock_repo.has_assistant_message_for.return_value = False
    with patch.object(chat_service, "_repo", mock_repo):
        offer = await chat_service._should_offer_root_cause_mode_choice(
            request, _conversation(FunctionType.SRA), FunctionType.SRA, ORGANIZATION_ID
        )
    assert offer is False


# --- Prompt ------------------------------------------------------------------


def test_guided_prompt_is_system_analysis_plus_override() -> None:
    guided = SYSTEM_PROMPTS[FunctionType.SYSTEM_GUIDED]
    assert guided.startswith(SYSTEM_ANALYSIS_PROMPT)
    assert guided.endswith(GUIDED_ROOT_CAUSE_ADDENDUM)
    assert 'Ask exactly one "why" question, then stop and wait' in guided


def test_guided_prompt_uses_the_organizations_system_analysis_prompt() -> None:
    prompts = DEFAULT_PROMPTS.model_copy(
        update={"system_analysis_prompt": "ORG SYSTEM ANALYSIS PROMPT"}
    )
    resolved = _resolve_prompt(FunctionType.SYSTEM_GUIDED, prompts)
    assert resolved == "ORG SYSTEM ANALYSIS PROMPT" + GUIDED_ROOT_CAUSE_ADDENDUM


def test_default_guided_chips_keep_the_flow_or_finish_it() -> None:
    block = _build_default_followups_block(FunctionType.SYSTEM_GUIDED)
    lines = [line for line in block.splitlines() if "|" in line]
    assert len(lines) == 4
    modes = [line.split("|")[1].strip() for line in lines]
    assert modes[0] == "system"
    assert modes[1:] == ["system_guided", "system_guided", "system_guided"]
