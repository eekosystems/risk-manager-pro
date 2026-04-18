"""Dual Risk Register infrastructure — FG RR <-> Client RR sync + ACP + closure approvals.

Per Sub-Prompt 4:
- Every risk record may have a "dual" — the same hazard tracked by both
  Faith Group (portfolio view) and a client airport (scoped view).
- Changes on either side enqueue a pending change for the other side to
  explicitly accept or reject. Nothing auto-applies.
- The FG RR maintains an Airport Context Profile per airport, enriched by
  internal FG corpus + external safety intelligence (ASRS, NOTAMs, etc.).
- High/Extreme records require Accountable Executive approval before close.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime  # noqa: TC003 — runtime required by SQLAlchemy Mapped[]

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LinkStatus(enum.StrEnum):
    ACTIVE = "active"
    BROKEN = "broken"  # one side was deleted


class PendingChangeType(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"


class PendingChangeDirection(enum.StrEnum):
    CLIENT_TO_FG = "client_to_fg"
    FG_TO_CLIENT = "fg_to_client"


class PendingChangeStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ACPDecision(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED_NEW_RECORD = "accepted_new_record"
    ACCEPTED_LINKED = "accepted_linked"
    ACCEPTED_MONITOR = "accepted_monitor"
    DISMISSED = "dismissed"


class ACPIntelligenceSource(enum.StrEnum):
    FAA_INCIDENT = "faa_incident"
    NASA_ASRS = "nasa_asrs"
    NOTAM = "notam"
    REGULATORY_ACTION = "regulatory_action"
    SAFETY_NEWS = "safety_news"
    MANUAL = "manual"


class ClosureApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskRecordLink(Base):
    """Pairing between an FG RR record and a client RR record for the same hazard.

    Both sides are rows in `risk_entries`, scoped by `organization_id` to the
    Faith Group platform org and the client airport's org respectively.
    """

    __tablename__ = "risk_record_links"
    __table_args__ = (
        UniqueConstraint(
            "fg_risk_entry_id",
            "client_risk_entry_id",
            name="uq_rr_link_pair",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fg_risk_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="CASCADE"), index=True
    )
    client_risk_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="CASCADE"), index=True
    )
    airport_identifier: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[LinkStatus] = mapped_column(
        String(20), default=LinkStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class PendingSyncChange(Base):
    """Queue of record changes waiting for review on the counterpart instance.

    When someone edits a dual record on one side, the RR writes a row here
    rather than applying the change to the other side. A consultant reviews
    the diff and explicitly accepts or rejects before it lands.
    """

    __tablename__ = "pending_sync_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    link_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("risk_record_links.id", ondelete="CASCADE"),
        index=True,
        default=None,
    )
    source_risk_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="CASCADE"), index=True
    )
    source_organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    target_organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    change_type: Mapped[PendingChangeType] = mapped_column(String(20))
    direction: Mapped[PendingChangeDirection] = mapped_column(String(20))
    status: Mapped[PendingChangeStatus] = mapped_column(
        String(20), default=PendingChangeStatus.PENDING.value, index=True
    )
    diff_json: Mapped[dict] = mapped_column(JSONB)  # {field: {old, new}}
    initiator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), default=None
    )
    review_note: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)


class AirportContextProfile(Base):
    """Per-airport institutional memory layer, maintained by Faith Group.

    One row per (organization_id, airport_identifier). The organization_id is
    always the Faith Group platform org — ACPs live on the FG side. Surfaced
    on the client airport's RR as a read-only reference layer.
    """

    __tablename__ = "airport_context_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "airport_identifier",
            name="uq_acp_per_airport",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    airport_identifier: Mapped[str] = mapped_column(String(20), index=True)

    # Free-form consultant-authored summary fields.
    system_profile: Mapped[str | None] = mapped_column(Text, default=None)
    known_risk_factors: Mapped[str | None] = mapped_column(Text, default=None)
    stakeholder_notes: Mapped[str | None] = mapped_column(Text, default=None)
    operational_impact_history: Mapped[str | None] = mapped_column(Text, default=None)

    # Structured bag for anything else (engagement history, runway config,
    # ATC notes) so we don't have to migrate every time a consultant wants
    # to capture a new dimension.
    extra_json: Mapped[dict | None] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class ACPIntelligenceItem(Base):
    """External safety event or occurrence flagged against an airport's ACP.

    Two-step human-in-the-loop per Sub-Prompt 4: Step 1 accept/dismiss into
    the ACP, Step 2 decide whether to create a hazard record, link to an
    existing one, or monitor without creating. Both steps require explicit
    FG consultant action — nothing auto-applies.
    """

    __tablename__ = "acp_intelligence_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    acp_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("airport_context_profiles.id", ondelete="CASCADE"), index=True
    )
    airport_identifier: Mapped[str] = mapped_column(String(20), index=True)
    source: Mapped[ACPIntelligenceSource] = mapped_column(String(40))
    headline: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    occurred_at: Mapped[datetime | None] = mapped_column(default=None)
    external_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    external_ref: Mapped[str | None] = mapped_column(String(255), default=None)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, default=None)

    decision: Mapped[ACPDecision] = mapped_column(
        String(40), default=ACPDecision.PENDING.value, index=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), default=None
    )
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    decision_note: Mapped[str | None] = mapped_column(Text, default=None)
    linked_risk_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="SET NULL"), default=None
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class ClosureApproval(Base):
    """Accountable Executive sign-off log for High/Extreme record closures.

    High/Extreme records cannot be moved to Closed status without a row here
    with status=APPROVED. The service layer enforces this gate.
    """

    __tablename__ = "closure_approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    risk_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("risk_entries.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    request_note: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[ClosureApprovalStatus] = mapped_column(
        String(20), default=ClosureApprovalStatus.PENDING.value, index=True
    )
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), default=None
    )
    approval_note: Mapped[str | None] = mapped_column(Text, default=None)
    requested_at: Mapped[datetime] = mapped_column(default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(default=None)
