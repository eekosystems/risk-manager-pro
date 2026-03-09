from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from datetime import datetime

    from app.models.organization_membership import OrganizationMembership


class InvitationStatus(enum.StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    PROVISIONED = "provisioned"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entra_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    invitation_status: Mapped[str] = mapped_column(
        String(20), default=InvitationStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(default=None)
    last_activity: Mapped[datetime | None] = mapped_column(default=None)

    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="user",
        foreign_keys="OrganizationMembership.user_id",
    )
