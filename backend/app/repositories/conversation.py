import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation, ConversationStatus, FunctionType
from app.models.message import Message, MessageRole
from app.models.user import User


def _strip_null_bytes(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [_strip_null_bytes(v) for v in value]
    if isinstance(value, dict):
        return {k: _strip_null_bytes(v) for k, v in value.items()}
    return value


# Chronological order with a deterministic tie-break. Messages written before
# the Python-side timestamp default share one `now()` per turn, so within a
# tie the user message (which always precedes the reply) sorts first: the
# `messagerole` enum declares user before assistant.
_MESSAGE_ORDER = (Message.created_at, Message.role, Message.id)


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        title: str = "New Conversation",
        function_type: FunctionType = FunctionType.GENERAL,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            organization_id=organization_id,
            title=title,
            function_type=function_type,
        )
        self._db.add(conversation)
        await self._db.flush()
        return conversation

    async def get_by_id(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
            )
            .options(selectinload(Conversation.messages))
        )
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_author(self, conversation: Conversation) -> User | None:
        """Fetch the User who owns the given conversation."""
        stmt = select(User).where(User.id == conversation.user_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.organization_id == organization_id,
                Conversation.status == ConversationStatus.ACTIVE,
            )
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        role: MessageRole,
        content: str,
        citations: list[dict[str, str]] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Message:
        conversation = await self.get_by_id(conversation_id, organization_id)
        if not conversation:
            raise NotFoundError("Conversation", str(conversation_id))

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=_strip_null_bytes(content),
            citations=_strip_null_bytes(citations),
            metadata_json=_strip_null_bytes(metadata),
        )
        self._db.add(message)
        await self._db.flush()
        return message

    async def get_messages(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        limit: int = 100,
    ) -> list[Message]:
        """The newest `limit` messages, oldest first.

        The window keeps the most recent turns: the model's history must end
        with the message it is replying to, so trimming has to drop the
        oldest messages, not the newest.
        """
        stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.conversation_id == conversation_id,
                Conversation.organization_id == organization_id,
            )
            .order_by(*(column.desc() for column in _MESSAGE_ORDER))
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        newest_first = list(result.scalars().all())
        newest_first.reverse()
        return newest_first

    async def has_assistant_message_for(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        function_types: Iterable[FunctionType],
    ) -> bool:
        """True when an assistant reply tagged with one of `function_types` exists.

        Assistant messages carry the function that produced them in
        `metadata_json["function_type"]`.
        """
        values = [ft.value for ft in function_types]
        stmt = (
            select(Message.id)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.conversation_id == conversation_id,
                Conversation.organization_id == organization_id,
                Message.role == MessageRole.ASSISTANT,
                Message.metadata_json["function_type"].astext.in_(values),
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def set_function_type(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        function_type: FunctionType,
    ) -> bool:
        conversation = await self.get_by_id(conversation_id, organization_id)
        if not conversation:
            return False
        if conversation.function_type == function_type:
            return False
        conversation.function_type = function_type
        await self._db.flush()
        return True

    async def archive(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        conversation = await self.get_by_id(conversation_id, organization_id, user_id=user_id)
        if not conversation:
            return False
        conversation.status = ConversationStatus.ARCHIVED
        await self._db.flush()
        return True
