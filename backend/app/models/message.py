import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


def utcnow_naive() -> datetime:
    """Current UTC time without tzinfo, matching the `timestamp` column type."""
    return datetime.now(UTC).replace(tzinfo=None)


class MessageRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, values_callable=lambda e: [x.value for x in e])
    )
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, default=None)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    # Set in Python, not by SQL `now()`: PostgreSQL's now() is fixed for the
    # whole transaction, and a chat turn writes the user message and the
    # assistant reply in one transaction. With identical timestamps the
    # history order between the two was unspecified, and the model could see
    # an answer attached to the wrong question.
    created_at: Mapped[datetime] = mapped_column(default=utcnow_naive)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
