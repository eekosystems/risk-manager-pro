import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationStatus
from app.models.document import Document
from app.models.message import Message


class SearchRepository:
    """Cross-resource search: case-insensitive substring match scoped by organization."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search_conversations(
        self,
        organization_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> list[tuple[Conversation, Message]]:
        """Return conversations whose messages match the query, paired with the first matched message."""
        like = f"%{query}%"
        stmt = (
            select(Conversation, Message)
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                Conversation.organization_id == organization_id,
                Conversation.status == ConversationStatus.ACTIVE,
                Message.content.ilike(like),
            )
            .order_by(Message.created_at.desc())
            .limit(limit * 4)
        )
        rows = (await self._db.execute(stmt)).all()

        seen: set[uuid.UUID] = set()
        results: list[tuple[Conversation, Message]] = []
        for conversation, message in rows:
            if conversation.id in seen:
                continue
            seen.add(conversation.id)
            results.append((conversation, message))
            if len(results) >= limit:
                break
        return results

    async def search_documents(
        self,
        organization_id: uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> list[Document]:
        like = f"%{query}%"
        stmt = (
            select(Document)
            .where(
                Document.organization_id == organization_id,
                Document.filename.ilike(like),
            )
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
