import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserNotificationPreference(Base):
    """Per-user QA/QC email opt-out flag (honors unsubscribe requests)."""

    __tablename__ = "user_notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
