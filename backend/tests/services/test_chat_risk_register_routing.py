"""Routing and prompt guarantees for the Risk Register entry flow.

The entry flow spans several turns: the model presents the record, the user
confirms, and the confirmation turn calls `save_risk_register_record`. Every
guarantee here exists so that turn still has the tool available.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, FunctionType
from app.schemas.chat import ChatRequest
from app.services.chat import (
    _RISK_REGISTER_TOOL_CONTRACT,
    ChatService,
    _build_default_followups_block,
)
from tests.conftest import ORGANIZATION_ID, make_test_user


def _conversation(function_type: FunctionType) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        user_id=make_test_user().id,
        organization_id=ORGANIZATION_ID,
        title="Hazard entry",
        function_type=function_type,
    )


@pytest.fixture
def chat_service(mock_openai_client: AsyncMock, mock_rag_service: AsyncMock) -> ChatService:
    return ChatService(
        db=AsyncMock(spec=AsyncSession),
        openai_client=mock_openai_client,
        rag_service=mock_rag_service,
    )


@pytest.mark.asyncio
async def test_confirm_chip_keeps_register_conversation_in_register(
    chat_service: ChatService,
) -> None:
    """A chip locked to GENERAL is how confirm chips arrive; the save turn must keep its tools."""
    request = ChatRequest(
        message="Confirm the Risk Register entry above is accurate and save it.",
        function_type=FunctionType.GENERAL,
        routing_locked=True,
    )
    routed = await chat_service._route_function_type(
        request, _conversation(FunctionType.RISK_REGISTER)
    )
    assert routed == FunctionType.RISK_REGISTER


@pytest.mark.asyncio
async def test_explicit_hop_out_of_register_is_honoured(chat_service: ChatService) -> None:
    request = ChatRequest(
        message="Run a Safety Risk Assessment on the hazard I just captured.",
        function_type=FunctionType.SRA,
        routing_locked=True,
    )
    routed = await chat_service._route_function_type(
        request, _conversation(FunctionType.RISK_REGISTER)
    )
    assert routed == FunctionType.SRA


@pytest.mark.asyncio
async def test_free_typed_reply_stays_in_register(chat_service: ChatService) -> None:
    request = ChatRequest(message="yes", function_type=FunctionType.GENERAL)
    with patch(
        "app.services.chat.classify_function",
        AsyncMock(return_value=FunctionType.GENERAL),
    ) as classify:
        routed = await chat_service._route_function_type(
            request, _conversation(FunctionType.RISK_REGISTER)
        )
    assert routed == FunctionType.RISK_REGISTER
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_locked_general_outside_register_is_unchanged(chat_service: ChatService) -> None:
    request = ChatRequest(
        message="Confirm the root cause findings above.",
        function_type=FunctionType.GENERAL,
        routing_locked=True,
    )
    routed = await chat_service._route_function_type(request, _conversation(FunctionType.PHL))
    assert routed == FunctionType.GENERAL


def test_default_register_chips_never_route_the_entry_to_general() -> None:
    block = _build_default_followups_block(FunctionType.RISK_REGISTER)
    for line in block.splitlines():
        if line.startswith("confirm") or line.startswith("validate"):
            assert "| risk_register |" in line
    assert "| general |" not in block


@pytest.mark.asyncio
async def test_register_turns_carry_the_tool_contract(chat_service: ChatService) -> None:
    mock_repo = AsyncMock()
    mock_repo.get_messages.return_value = []
    mock_guidance = AsyncMock()
    mock_guidance.build_prompt_block.return_value = ""
    with (
        patch.object(chat_service, "_repo", mock_repo),
        patch.object(chat_service, "_guidance", mock_guidance),
    ):
        register = await chat_service._prepare_messages(
            conversation_id=uuid.uuid4(),
            organization_id=ORGANIZATION_ID,
            function_type=FunctionType.RISK_REGISTER,
            prompts_config=None,
            context_block="",
        )
        general = await chat_service._prepare_messages(
            conversation_id=uuid.uuid4(),
            organization_id=ORGANIZATION_ID,
            function_type=FunctionType.GENERAL,
            prompts_config=None,
            context_block="",
        )

    register_system = [m["content"] for m in register if m["role"] == "system"]
    general_system = [m["content"] for m in general if m["role"] == "system"]
    assert _RISK_REGISTER_TOOL_CONTRACT in register_system
    assert _RISK_REGISTER_TOOL_CONTRACT not in general_system
    assert "save_risk_register_record" in _RISK_REGISTER_TOOL_CONTRACT
