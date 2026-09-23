import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.risk import RiskLevel


class ResidualAssessmentStatus(enum.StrEnum):
    """Lifecycle of one SP3 residual re-assessment of a risk entry.

    pending -> proposed | failed; proposed -> confirmed | dismissed.
    Any pending or proposed run becomes superseded when a newer run is
    requested for the same entry, so only the latest mitigation set can
    reach the record.
    """

    PENDING = "pending"
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


OPEN_ASSESSMENT_STATUSES: frozenset[ResidualAssessmentStatus] = frozenset(
    {ResidualAssessmentStatus.PENDING, ResidualAssessmentStatus.PROPOSED}
)


class ResidualAssessment(Base):
    __tablename__ = "residual_assessments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    risk_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ResidualAssessmentStatus] = mapped_column(
        Enum(ResidualAssessmentStatus, values_callable=lambda e: [x.value for x in e]),
        default=ResidualAssessmentStatus.PENDING,
    )
    # What caused the run, e.g. "mitigation.created" or "manual".
    trigger: Mapped[str] = mapped_column(String(50))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)

    # Proposed residual cell (stored severity 1=Minimal..5=Catastrophic).
    residual_severity: Mapped[int | None] = mapped_column(default=None)
    residual_likelihood: Mapped[str | None] = mapped_column(String(1), default=None)
    residual_risk_level: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, values_callable=lambda e: [x.value for x in e]),
        default=None,
    )
    # Five-tier breakdown, ALARP status, rationale and cited sources.
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    error_code: Mapped[str | None] = mapped_column(String(50), default=None)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
