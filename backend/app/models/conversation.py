from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.message import Message


class FunctionType(str, enum.Enum):
    PHL = "phl"
    SRA = "sra"
    SYSTEM_ANALYSIS = "system"
    GENERAL = "general"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), default="New Conversation")
    function_type: Mapped[FunctionType] = mapped_column(
        Enum(FunctionType), default=FunctionType.GENERAL
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus), default=ConversationStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    messages: Mapped[list[Message]] = relationship(back_populates="conversation")
