import enum
import uuid
from datetime import datetime  # noqa: TCH003
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class MembershipRole(enum.StrEnum):
    ORG_ADMIN = "org_admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, values_callable=lambda e: [x.value for x in e]),
        default=MembershipRole.VIEWER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User"] = relationship(
        back_populates="memberships",
        foreign_keys=[user_id],
    )
    organization: Mapped["Organization"] = relationship(
        back_populates="memberships",
    )
