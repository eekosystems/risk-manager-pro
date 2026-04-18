import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationType(enum.StrEnum):
    CHAT_RESPONSE = "chat_response"
    RISK_CREATED = "risk_created"
    RISK_UPDATED = "risk_updated"
    MITIGATION_CREATED = "mitigation_created"
    DOCUMENT_INDEXED = "document_indexed"
    RISK_THRESHOLD_EXCEEDED = "risk_threshold_exceeded"
    SYNC_PENDING_REVIEW = "sync_pending_review"
    ACP_FLAG_RAISED = "acp_flag_raised"
    CLOSURE_APPROVAL_REQUESTED = "closure_approval_requested"
    CLOSURE_APPROVAL_DECIDED = "closure_approval_decided"


class DeliveryChannel(enum.StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"


class DeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    triggered_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, values_callable=lambda e: [x.value for x in e]),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(255), default=None)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), index=True)


class NotificationDeliveryLog(Base):
    """Per-channel delivery record for a notification (audit + retry support)."""

    __tablename__ = "notification_delivery_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[DeliveryChannel] = mapped_column(
        Enum(DeliveryChannel, values_callable=lambda e: [x.value for x in e])
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, values_callable=lambda e: [x.value for x in e]),
        index=True,
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
