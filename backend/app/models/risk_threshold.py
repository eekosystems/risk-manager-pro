import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RiskAlertThreshold(Base):
    """Per-organization threshold that triggers notifications when open
    risks at a given level exceed a numeric cap."""

    __tablename__ = "risk_alert_thresholds"
    __table_args__ = (UniqueConstraint("organization_id", "risk_level", name="uq_org_risk_level"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    risk_level: Mapped[str] = mapped_column(String(10))
    max_open_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
