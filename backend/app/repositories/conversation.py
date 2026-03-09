import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation, ConversationStatus, FunctionType
from app.models.message import Message, MessageRole


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
        self, conversation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
            )
            .options(selectinload(Conversation.messages))
        )
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
            content=content,
            citations=citations,
            metadata_json=metadata,
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
        stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.conversation_id == conversation_id,
                Conversation.organization_id == organization_id,
            )
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def archive(self, conversation_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        conversation = await self.get_by_id(conversation_id, organization_id)
        if not conversation:
            return False
        conversation.status = ConversationStatus.ARCHIVED
        await self._db.flush()
        return True
