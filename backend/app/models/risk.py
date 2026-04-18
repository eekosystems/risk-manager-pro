import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RiskStatus(enum.StrEnum):
    """Legacy status field — retained for existing records.

    New code should prefer `RecordStatus`. Both are kept in sync by the
    service layer during the transition.
    """

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
    EXTREME = "extreme"


class OperationalDomain(enum.StrEnum):
    MOVEMENT_AREA = "movement_area"
    NON_MOVEMENT_AREA = "non_movement_area"
    RAMP = "ramp"
    TERMINAL = "terminal"
    LANDSIDE = "landside"
    USER_DEFINED = "user_defined"


class HazardCategory5M(enum.StrEnum):
    HUMAN = "human"
    MACHINE = "machine"
    MEDIUM = "medium"
    MISSION = "mission"
    MANAGEMENT = "management"


class HazardCategoryICAO(enum.StrEnum):
    TECHNICAL = "technical"
    HUMAN = "human"
    ORGANIZATIONAL = "organizational"
    ENVIRONMENTAL = "environmental"


CATEGORY_5M_TO_ICAO_DEFAULT: dict[HazardCategory5M, HazardCategoryICAO] = {
    HazardCategory5M.HUMAN: HazardCategoryICAO.HUMAN,
    HazardCategory5M.MACHINE: HazardCategoryICAO.TECHNICAL,
    HazardCategory5M.MEDIUM: HazardCategoryICAO.ENVIRONMENTAL,
    HazardCategory5M.MISSION: HazardCategoryICAO.ORGANIZATIONAL,
    HazardCategory5M.MANAGEMENT: HazardCategoryICAO.ORGANIZATIONAL,
}


class RiskMatrixApplied(enum.StrEnum):
    AIRPORT_SPECIFIC = "airport_specific"
    FAA_5X5 = "faa_5x5"
    CONSERVATIVE_DEFAULT = "conservative_default"


class RecordStatus(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_ASSESSMENT = "pending_assessment"
    CLOSED = "closed"
    MONITORING = "monitoring"


class ValidationStatus(enum.StrEnum):
    RMP_VALIDATED = "rmp_validated"
    USER_REPORTED = "user_reported"
    PENDING = "pending"


class RecordSource(enum.StrEnum):
    RMP_SP1 = "rmp_sp1"
    RMP_SP2 = "rmp_sp2"
    RMP_SP3 = "rmp_sp3"
    RMP_SP4 = "rmp_sp4"
    MANUAL_ENTRY = "manual_entry"
    FG_PUSH = "fg_push"
    CLIENT_PUSH = "client_push"


class SyncStatus(enum.StrEnum):
    FG_ONLY = "fg_only"
    CLIENT_ONLY = "client_only"
    DUAL_IN_SYNC = "dual_in_sync"
    DUAL_PENDING = "dual_pending"


LEGACY_STATUS_TO_RECORD_STATUS: dict[RiskStatus, RecordStatus] = {
    RiskStatus.OPEN: RecordStatus.OPEN,
    RiskStatus.MITIGATING: RecordStatus.IN_PROGRESS,
    RiskStatus.CLOSED: RecordStatus.CLOSED,
    RiskStatus.ACCEPTED: RecordStatus.MONITORING,
}


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


def default_icao_for_5m(category: HazardCategory5M) -> HazardCategoryICAO:
    """Suggested ICAO category for a given 5M selection, per Sub-Prompt 4."""
    return CATEGORY_5M_TO_ICAO_DEFAULT[category]


def record_status_from_legacy(status: RiskStatus) -> RecordStatus:
    """Map the legacy RiskStatus to the Sub-Prompt 4 RecordStatus."""
    return LEGACY_STATUS_TO_RECORD_STATUS[status]


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

    # --- Sub-Prompt 4 / Risk Register schema extensions ---
    airport_identifier: Mapped[str | None] = mapped_column(String(20), default=None, index=True)
    potential_credible_outcome: Mapped[str | None] = mapped_column(Text, default=None)
    operational_domain: Mapped[OperationalDomain | None] = mapped_column(
        Enum(OperationalDomain, values_callable=lambda e: [x.value for x in e]),
        default=None,
    )
    sub_location: Mapped[str | None] = mapped_column(String(255), default=None)
    hazard_category_5m: Mapped[HazardCategory5M | None] = mapped_column(
        Enum(HazardCategory5M, values_callable=lambda e: [x.value for x in e]),
        default=None,
    )
    hazard_category_icao: Mapped[HazardCategoryICAO | None] = mapped_column(
        Enum(HazardCategoryICAO, values_callable=lambda e: [x.value for x in e]),
        default=None,
    )
    risk_matrix_applied: Mapped[RiskMatrixApplied] = mapped_column(
        Enum(RiskMatrixApplied, values_callable=lambda e: [x.value for x in e]),
        default=RiskMatrixApplied.FAA_5X5,
    )
    existing_controls: Mapped[str | None] = mapped_column(Text, default=None)
    residual_risk_level: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, values_callable=lambda e: [x.value for x in e]),
        default=None,
    )
    record_status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus, values_callable=lambda e: [x.value for x in e]),
        default=RecordStatus.OPEN,
    )
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, values_callable=lambda e: [x.value for x in e]),
        default=ValidationStatus.PENDING,
    )
    source: Mapped[RecordSource] = mapped_column(
        Enum(RecordSource, values_callable=lambda e: [x.value for x in e]),
        default=RecordSource.MANUAL_ENTRY,
    )
    sync_status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, values_callable=lambda e: [x.value for x in e]),
        default=SyncStatus.FG_ONLY,
    )
    acm_cross_reference: Mapped[str | None] = mapped_column(Text, default=None)
    related_record_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), default=None
    )
    audit_trail_json: Mapped[dict | None] = mapped_column(JSONB, default=None)

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
    verification_method: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[MitigationStatus] = mapped_column(
        Enum(MitigationStatus, values_callable=lambda e: [x.value for x in e]),
        default=MitigationStatus.PENDING,
    )
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    risk_entry: Mapped["RiskEntry"] = relationship(back_populates="mitigations")


class AirportSubLocation(Base):
    """Airport-specific sub-location library (per Sub-Prompt 4 §Step 3a).

    Scoped by organization + airport identifier. Populated opportunistically
    as users enter sub-locations during Risk Register entry; surfaced as
    suggestions on subsequent entries for the same airport.
    """

    __tablename__ = "airport_sub_locations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "airport_identifier",
            "name",
            name="uq_airport_sub_location",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    airport_identifier: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
