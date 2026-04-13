import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkflowType(enum.StrEnum):
    PHL = "phl"
    SRA = "sra"


class WorkflowStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[WorkflowType] = mapped_column(
        Enum(WorkflowType, values_callable=lambda e: [x.value for x in e]),
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, values_callable=lambda e: [x.value for x in e]),
        default=WorkflowStatus.DRAFT,
    )
    title: Mapped[str] = mapped_column(String(500), default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        default=None,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(default=None)
    approved_at: Mapped[datetime | None] = mapped_column(default=None)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    risk_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="SET NULL"),
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
