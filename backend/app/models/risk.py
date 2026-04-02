import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RiskStatus(enum.StrEnum):
    OPEN = "open"
    MITIGATING = "mitigating"
    CLOSED = "closed"
    ACCEPTED = "accepted"


class Severity(enum.IntEnum):
    MINIMAL = 1
    MINOR = 2
    MAJOR = 3
    HAZARDOUS = 4
    CATASTROPHIC = 5


class Likelihood(enum.StrEnum):
    FREQUENT = "A"
    PROBABLE = "B"
    REMOTE = "C"
    EXTREMELY_REMOTE = "D"
    EXTREMELY_IMPROBABLE = "E"


class RiskLevel(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# FAA Order 8040.4B risk matrix: RISK_MATRIX[likelihood][severity] -> RiskLevel
RISK_MATRIX: dict[str, dict[int, RiskLevel]] = {
    "A": {
        1: RiskLevel.MEDIUM,
        2: RiskLevel.HIGH,
        3: RiskLevel.HIGH,
        4: RiskLevel.HIGH,
        5: RiskLevel.HIGH,
    },
    "B": {
        1: RiskLevel.LOW,
        2: RiskLevel.MEDIUM,
        3: RiskLevel.HIGH,
        4: RiskLevel.HIGH,
        5: RiskLevel.HIGH,
    },
    "C": {
        1: RiskLevel.LOW,
        2: RiskLevel.LOW,
        3: RiskLevel.MEDIUM,
        4: RiskLevel.HIGH,
        5: RiskLevel.HIGH,
    },
    "D": {
        1: RiskLevel.LOW,
        2: RiskLevel.LOW,
        3: RiskLevel.MEDIUM,
        4: RiskLevel.MEDIUM,
        5: RiskLevel.HIGH,
    },
    "E": {
        1: RiskLevel.LOW,
        2: RiskLevel.LOW,
        3: RiskLevel.LOW,
        4: RiskLevel.LOW,
        5: RiskLevel.MEDIUM,
    },
}


def compute_risk_level(severity: int, likelihood: str) -> RiskLevel:
    """Compute the risk level from the FAA 5x5 matrix."""
    return RISK_MATRIX[likelihood][severity]


class MitigationStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RiskEntry(Base):
    __tablename__ = "risk_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    hazard: Mapped[str] = mapped_column(Text)
    severity: Mapped[int] = mapped_column()
    likelihood: Mapped[str] = mapped_column(String(1))
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, values_callable=lambda e: [x.value for x in e]),
    )
    status: Mapped[RiskStatus] = mapped_column(
        Enum(RiskStatus, values_callable=lambda e: [x.value for x in e]),
        default=RiskStatus.OPEN,
    )
    function_type: Mapped[str] = mapped_column(String(20), default="general")
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        default=None,
    )
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    mitigations: Mapped[list["Mitigation"]] = relationship(
        back_populates="risk_entry", cascade="all, delete-orphan"
    )


class Mitigation(Base):
    __tablename__ = "mitigations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    risk_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    assignee: Mapped[str | None] = mapped_column(String(255), default=None)
    due_date: Mapped[datetime | None] = mapped_column(default=None)
    status: Mapped[MitigationStatus] = mapped_column(
        Enum(MitigationStatus, values_callable=lambda e: [x.value for x in e]),
        default=MitigationStatus.PENDING,
    )
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    risk_entry: Mapped["RiskEntry"] = relationship(back_populates="mitigations")
