import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.conversation import FunctionType


class GuidanceScope(enum.StrEnum):
    """How far a guidance rule reaches."""

    GLOBAL = "global"
    ORGANIZATION = "organization"


class ApplicationGuidance(Base):
    """A curated rule injected into the system prompt on every matching answer.

    This is the application's permanent memory. Rules are written by platform
    admins — usually by promoting a piece of user feedback — and take effect on
    the next message, with no training run. Each one stays individually
    editable and revocable so a bad rule can be withdrawn immediately and the
    change is attributable, which fine-tuning could not offer.
    """

    __tablename__ = "application_guidance"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[GuidanceScope] = mapped_column(
        Enum(GuidanceScope, values_callable=lambda e: [x.value for x in e]),
        index=True,
    )
    # Null for global rules, which apply to every tenant.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), default=None, index=True
    )
    # Null means the rule applies to every function type.
    function_type: Mapped[FunctionType | None] = mapped_column(
        Enum(FunctionType, values_callable=lambda e: [x.value for x in e]),
        default=None,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text)
    # The feedback this rule was promoted from, when it came from one.
    source_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("message_feedback.id", ondelete="SET NULL"), default=None
    )
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
