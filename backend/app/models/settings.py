import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    settings_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        # One settings row per category per org
        {"comment": "Per-organization settings by category"},
    )
