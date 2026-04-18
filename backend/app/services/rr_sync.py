"""Dual Risk Register sync orchestration, ACP management, closure approvals.

The invariants enforced here:
- Faith Group platform org is the authoritative side. When either side
  creates a record, a twin is pushed to the counterpart org as a
  PendingSyncChange of type CREATE — the target org must explicitly accept
  before the twin record actually materializes.
- Updates to a dual record enqueue an UPDATE PendingSyncChange. No auto-apply.
- High/Extreme closures require an approved ClosureApproval row.
- ACP intelligence requires two explicit FG consultant decisions (accept
  into ACP, then decide: new record / link / monitor).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.core.exceptions import AppError, NotFoundError
from app.models.organization import Organization
from app.models.risk import RecordSource, RecordStatus, RiskEntry, RiskLevel
from app.models.rr_sync import (
    ACPDecision,
    ACPIntelligenceItem,
    AirportContextProfile,
    ClosureApproval,
    ClosureApprovalStatus,
    LinkStatus,
    PendingChangeDirection,
    PendingChangeStatus,
    PendingChangeType,
    PendingSyncChange,
    RiskRecordLink,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


# Fields that trigger a sync diff when they change on a dual record.
SYNCABLE_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "hazard",
    "severity",
    "likelihood",
    "risk_level",
    "status",
    "record_status",
    "notes",
    "airport_identifier",
    "potential_credible_outcome",
    "operational_domain",
    "sub_location",
    "hazard_category_5m",
    "hazard_category_icao",
    "existing_controls",
    "residual_risk_level",
    "validation_status",
    "acm_cross_reference",
)


class RRSyncError(AppError):
    """Raised when a sync operation cannot proceed."""

    def __init__(self, message: str, code: str = "RR_SYNC_ERROR") -> None:
        super().__init__(code=code, message=message, status_code=400)


class ClosureGateError(AppError):
    """Raised when a High/Extreme record is closed without an approved AE sign-off."""

    def __init__(self, message: str) -> None:
        super().__init__(code="CLOSURE_REQUIRES_AE", message=message, status_code=403)


class RRSyncService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Platform org resolution
    # ------------------------------------------------------------------

    async def _get_platform_org_id(self) -> uuid.UUID | None:
        stmt = select(Organization.id).where(Organization.is_platform.is_(True)).limit(1)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _is_platform_org(self, organization_id: uuid.UUID) -> bool:
        stmt = select(Organization.is_platform).where(Organization.id == organization_id)
        result = await self._db.execute(stmt)
        return bool(result.scalar_one_or_none())

    # ------------------------------------------------------------------
    # Create-time push
    # ------------------------------------------------------------------

    async def enqueue_create_push(
        self,
        *,
        entry: RiskEntry,
        creator_user_id: uuid.UUID,
    ) -> PendingSyncChange | None:
        """Called after a new RiskEntry is persisted.

        - If the creator org is a client: enqueue a push to the FG platform org.
        - If the creator org is the platform: push to the client airport's org
          when one can be resolved from `airport_identifier` (match by slug).
        - Otherwise returns None (no counterpart to push to).

        The counterpart record is NOT created here. It materializes only when
        the target org accepts the pending change via accept_pending_change().
        """
        platform_org_id = await self._get_platform_org_id()
        if platform_org_id is None:
            logger.info("rr_sync_no_platform_org_configured")
            return None

        is_platform = entry.organization_id == platform_org_id
        target_org_id: uuid.UUID | None = None
        direction: PendingChangeDirection

        if is_platform:
            # FG created a record — route to matching client org if one exists.
            if not entry.airport_identifier:
                return None
            client_id = await self._resolve_client_org_for_airport(entry.airport_identifier)
            if client_id is None:
                return None
            target_org_id = client_id
            direction = PendingChangeDirection.FG_TO_CLIENT
        else:
            # Client created — always push to FG.
            target_org_id = platform_org_id
            direction = PendingChangeDirection.CLIENT_TO_FG

        snapshot = _snapshot_entry(entry)
        pending = PendingSyncChange(
            link_id=None,
            source_risk_entry_id=entry.id,
            source_organization_id=entry.organization_id,
            target_organization_id=target_org_id,
            change_type=PendingChangeType.CREATE,
            direction=direction,
            status=PendingChangeStatus.PENDING,
            diff_json={"create": snapshot},
            initiator_user_id=creator_user_id,
        )
        self._db.add(pending)
        await self._db.flush()
        logger.info(
            "rr_sync_create_push_enqueued",
            source_risk_id=str(entry.id),
            direction=direction.value,
            target_org=str(target_org_id),
        )
        return pending

    async def enqueue_update_push(
        self,
        *,
        entry: RiskEntry,
        diff: dict[str, dict[str, Any]],
        initiator_user_id: uuid.UUID,
    ) -> PendingSyncChange | None:
        """Called after a dual record is updated. Enqueues a diff on the twin."""
        if not diff:
            return None
        link = await self._find_link_for_entry(entry.id)
        if link is None:
            return None
        twin_id = (
            link.client_risk_entry_id
            if entry.id == link.fg_risk_entry_id
            else link.fg_risk_entry_id
        )
        twin_stmt = select(RiskEntry.organization_id).where(RiskEntry.id == twin_id)
        twin_org_id = (await self._db.execute(twin_stmt)).scalar_one()
        platform_org_id = await self._get_platform_org_id()
        direction = (
            PendingChangeDirection.CLIENT_TO_FG
            if platform_org_id is not None and twin_org_id == platform_org_id
            else PendingChangeDirection.FG_TO_CLIENT
        )
        pending = PendingSyncChange(
            link_id=link.id,
            source_risk_entry_id=entry.id,
            source_organization_id=entry.organization_id,
            target_organization_id=twin_org_id,
            change_type=PendingChangeType.UPDATE,
            direction=direction,
            status=PendingChangeStatus.PENDING,
            diff_json={"update": diff},
            initiator_user_id=initiator_user_id,
        )
        self._db.add(pending)
        await self._db.flush()
        logger.info(
            "rr_sync_update_push_enqueued",
            source_risk_id=str(entry.id),
            changed_fields=list(diff.keys()),
        )
        return pending

    async def _resolve_client_org_for_airport(self, airport_identifier: str) -> uuid.UUID | None:
        """Match airport identifier to a client organization by slug.

        Convention: a client airport's organization `slug` equals its ICAO/FAA
        identifier (case-insensitive). This matches how onboarding creates
        client orgs. If no match exists, the push is skipped (FG-only record).
        """
        slug_lc = airport_identifier.lower()
        stmt = select(Organization.id).where(
            Organization.is_platform.is_(False),
            Organization.status == "active",
        )
        result = await self._db.execute(stmt)
        for (org_id,) in result.all():
            org_stmt = select(Organization).where(Organization.id == org_id)
            org = (await self._db.execute(org_stmt)).scalar_one()
            if (org.slug or "").lower() == slug_lc:
                return org.id
        return None

    async def _find_link_for_entry(self, risk_entry_id: uuid.UUID) -> RiskRecordLink | None:
        stmt = select(RiskRecordLink).where(
            (RiskRecordLink.fg_risk_entry_id == risk_entry_id)
            | (RiskRecordLink.client_risk_entry_id == risk_entry_id)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Review queue
    # ------------------------------------------------------------------

    async def list_pending_changes(
        self,
        *,
        organization_id: uuid.UUID,
        status: PendingChangeStatus | None = PendingChangeStatus.PENDING,
    ) -> list[PendingSyncChange]:
        stmt = select(PendingSyncChange).where(
            PendingSyncChange.target_organization_id == organization_id
        )
        if status:
            stmt = stmt.where(PendingSyncChange.status == status)
        stmt = stmt.order_by(PendingSyncChange.created_at.desc())
        return list((await self._db.execute(stmt)).scalars().all())

    async def accept_pending_change(
        self,
        *,
        pending_id: uuid.UUID,
        reviewer_user_id: uuid.UUID,
        reviewer_org_id: uuid.UUID,
        note: str | None = None,
    ) -> PendingSyncChange:
        pending = await self._get_pending(pending_id, reviewer_org_id)
        if pending.change_type == PendingChangeType.CREATE:
            await self._materialize_created_twin(pending, reviewer_user_id)
        elif pending.change_type == PendingChangeType.UPDATE:
            await self._apply_update_diff(pending)
        elif pending.change_type == PendingChangeType.CLOSE:
            await self._apply_close_push(pending)

        pending.status = PendingChangeStatus.ACCEPTED
        pending.reviewer_user_id = reviewer_user_id
        pending.review_note = note
        pending.reviewed_at = datetime.now(UTC)
        await self._db.flush()
        logger.info(
            "rr_sync_change_accepted",
            pending_id=str(pending_id),
            change_type=pending.change_type.value,
        )
        return pending

    async def reject_pending_change(
        self,
        *,
        pending_id: uuid.UUID,
        reviewer_user_id: uuid.UUID,
        reviewer_org_id: uuid.UUID,
        note: str | None = None,
    ) -> PendingSyncChange:
        pending = await self._get_pending(pending_id, reviewer_org_id)
        pending.status = PendingChangeStatus.REJECTED
        pending.reviewer_user_id = reviewer_user_id
        pending.review_note = note
        pending.reviewed_at = datetime.now(UTC)
        await self._db.flush()
        logger.info("rr_sync_change_rejected", pending_id=str(pending_id))
        return pending

    async def _get_pending(
        self, pending_id: uuid.UUID, reviewer_org_id: uuid.UUID
    ) -> PendingSyncChange:
        stmt = select(PendingSyncChange).where(PendingSyncChange.id == pending_id)
        row = (await self._db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundError("PendingSyncChange", str(pending_id))
        if row.target_organization_id != reviewer_org_id:
            raise RRSyncError("This change belongs to a different organization.")
        if row.status != PendingChangeStatus.PENDING:
            raise RRSyncError(f"Change is already {row.status.value}; cannot re-review.")
        return row

    async def _materialize_created_twin(
        self, pending: PendingSyncChange, reviewer_user_id: uuid.UUID
    ) -> None:
        """Create the counterpart record and link it to the original."""
        snapshot = pending.diff_json.get("create", {})
        source_stmt = select(RiskEntry).where(RiskEntry.id == pending.source_risk_entry_id)
        source = (await self._db.execute(source_stmt)).scalar_one_or_none()
        if source is None:
            raise RRSyncError("Source record no longer exists; cannot materialize twin.")

        twin = RiskEntry(
            organization_id=pending.target_organization_id,
            created_by=reviewer_user_id,
            title=snapshot.get("title", source.title),
            description=snapshot.get("description", source.description),
            hazard=snapshot.get("hazard", source.hazard),
            severity=snapshot.get("severity", source.severity),
            likelihood=snapshot.get("likelihood", source.likelihood),
            risk_level=snapshot.get("risk_level", source.risk_level),
            function_type=source.function_type,
            notes=snapshot.get("notes", source.notes),
            airport_identifier=snapshot.get("airport_identifier", source.airport_identifier),
            potential_credible_outcome=snapshot.get(
                "potential_credible_outcome", source.potential_credible_outcome
            ),
            operational_domain=snapshot.get("operational_domain", source.operational_domain),
            sub_location=snapshot.get("sub_location", source.sub_location),
            hazard_category_5m=snapshot.get("hazard_category_5m", source.hazard_category_5m),
            hazard_category_icao=snapshot.get("hazard_category_icao", source.hazard_category_icao),
            risk_matrix_applied=snapshot.get("risk_matrix_applied", source.risk_matrix_applied),
            existing_controls=snapshot.get("existing_controls", source.existing_controls),
            residual_risk_level=snapshot.get("residual_risk_level", source.residual_risk_level),
            record_status=snapshot.get("record_status", source.record_status),
            validation_status=snapshot.get("validation_status", source.validation_status),
            source=(
                RecordSource.FG_PUSH
                if pending.direction == PendingChangeDirection.FG_TO_CLIENT
                else RecordSource.CLIENT_PUSH
            ),
            acm_cross_reference=snapshot.get("acm_cross_reference", source.acm_cross_reference),
        )
        self._db.add(twin)
        await self._db.flush()

        # FG side is always the "fg" side of the link.
        platform_org_id = await self._get_platform_org_id()
        if platform_org_id is not None and source.organization_id == platform_org_id:
            fg_id, client_id = source.id, twin.id
        else:
            fg_id, client_id = twin.id, source.id

        link = RiskRecordLink(
            fg_risk_entry_id=fg_id,
            client_risk_entry_id=client_id,
            airport_identifier=snapshot.get("airport_identifier", source.airport_identifier or ""),
            status=LinkStatus.ACTIVE,
        )
        self._db.add(link)
        await self._db.flush()
        pending.link_id = link.id

        # Keep sync_status in sync on both sides.
        source.sync_status = "dual_in_sync"  # type: ignore[assignment]
        twin.sync_status = "dual_in_sync"  # type: ignore[assignment]
        await self._db.flush()

    async def _apply_update_diff(self, pending: PendingSyncChange) -> None:
        if pending.link_id is None:
            raise RRSyncError("Update change has no link — cannot apply.")
        link_stmt = select(RiskRecordLink).where(RiskRecordLink.id == pending.link_id)
        link = (await self._db.execute(link_stmt)).scalar_one()
        twin_id = (
            link.client_risk_entry_id
            if pending.source_risk_entry_id == link.fg_risk_entry_id
            else link.fg_risk_entry_id
        )
        twin_stmt = select(RiskEntry).where(RiskEntry.id == twin_id)
        twin = (await self._db.execute(twin_stmt)).scalar_one()
        for field, change in pending.diff_json.get("update", {}).items():
            if field in SYNCABLE_FIELDS and "new" in change:
                setattr(twin, field, change["new"])
        await self._db.flush()

    async def _apply_close_push(self, pending: PendingSyncChange) -> None:
        if pending.link_id is None:
            return
        link_stmt = select(RiskRecordLink).where(RiskRecordLink.id == pending.link_id)
        link = (await self._db.execute(link_stmt)).scalar_one()
        twin_id = (
            link.client_risk_entry_id
            if pending.source_risk_entry_id == link.fg_risk_entry_id
            else link.fg_risk_entry_id
        )
        twin_stmt = select(RiskEntry).where(RiskEntry.id == twin_id)
        twin = (await self._db.execute(twin_stmt)).scalar_one()
        twin.record_status = RecordStatus.CLOSED  # type: ignore[assignment]
        await self._db.flush()

    # ------------------------------------------------------------------
    # ACP
    # ------------------------------------------------------------------

    async def get_or_create_acp(
        self, organization_id: uuid.UUID, airport_identifier: str
    ) -> AirportContextProfile:
        stmt = select(AirportContextProfile).where(
            AirportContextProfile.organization_id == organization_id,
            AirportContextProfile.airport_identifier == airport_identifier,
        )
        existing = (await self._db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing
        row = AirportContextProfile(
            organization_id=organization_id,
            airport_identifier=airport_identifier,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def update_acp(
        self,
        *,
        acp_id: uuid.UUID,
        organization_id: uuid.UUID,
        **fields: Any,
    ) -> AirportContextProfile:
        stmt = select(AirportContextProfile).where(
            AirportContextProfile.id == acp_id,
            AirportContextProfile.organization_id == organization_id,
        )
        acp = (await self._db.execute(stmt)).scalar_one_or_none()
        if acp is None:
            raise NotFoundError("AirportContextProfile", str(acp_id))
        for k, v in fields.items():
            if v is not None and hasattr(acp, k):
                setattr(acp, k, v)
        await self._db.flush()
        return acp

    async def add_intelligence_item(
        self,
        *,
        organization_id: uuid.UUID,
        airport_identifier: str,
        source: str,
        headline: str,
        summary: str | None,
        occurred_at: datetime | None,
        external_url: str | None,
        external_ref: str | None,
        raw_payload: dict | None,
        created_by: uuid.UUID | None,
    ) -> ACPIntelligenceItem:
        acp = await self.get_or_create_acp(organization_id, airport_identifier)
        item = ACPIntelligenceItem(
            acp_id=acp.id,
            airport_identifier=airport_identifier,
            source=source,
            headline=headline,
            summary=summary,
            occurred_at=occurred_at,
            external_url=external_url,
            external_ref=external_ref,
            raw_payload=raw_payload,
            created_by=created_by,
        )
        self._db.add(item)
        await self._db.flush()
        logger.info(
            "acp_intelligence_added",
            airport=airport_identifier,
            source=source,
            headline=headline[:80],
        )
        return item

    async def list_intelligence_items(
        self,
        *,
        organization_id: uuid.UUID,
        airport_identifier: str | None = None,
        decision: ACPDecision | None = None,
    ) -> list[ACPIntelligenceItem]:
        stmt = (
            select(ACPIntelligenceItem)
            .join(AirportContextProfile, ACPIntelligenceItem.acp_id == AirportContextProfile.id)
            .where(AirportContextProfile.organization_id == organization_id)
        )
        if airport_identifier:
            stmt = stmt.where(ACPIntelligenceItem.airport_identifier == airport_identifier)
        if decision:
            stmt = stmt.where(ACPIntelligenceItem.decision == decision)
        stmt = stmt.order_by(ACPIntelligenceItem.created_at.desc())
        return list((await self._db.execute(stmt)).scalars().all())

    async def decide_intelligence_item(
        self,
        *,
        item_id: uuid.UUID,
        organization_id: uuid.UUID,
        decision: ACPDecision,
        decided_by: uuid.UUID,
        note: str | None,
        linked_risk_entry_id: uuid.UUID | None = None,
    ) -> ACPIntelligenceItem:
        stmt = (
            select(ACPIntelligenceItem)
            .join(AirportContextProfile, ACPIntelligenceItem.acp_id == AirportContextProfile.id)
            .where(
                ACPIntelligenceItem.id == item_id,
                AirportContextProfile.organization_id == organization_id,
            )
        )
        item = (await self._db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise NotFoundError("ACPIntelligenceItem", str(item_id))
        if item.decision != ACPDecision.PENDING:
            raise RRSyncError(
                f"Item already decided as {item.decision.value}; re-open by adding a new item."
            )
        item.decision = decision
        item.decision_note = note
        item.decided_by = decided_by
        item.decided_at = datetime.now(UTC)
        if linked_risk_entry_id:
            item.linked_risk_entry_id = linked_risk_entry_id
        await self._db.flush()
        logger.info(
            "acp_intelligence_decided",
            item_id=str(item_id),
            decision=decision.value,
        )
        return item

    # ------------------------------------------------------------------
    # Closure approvals
    # ------------------------------------------------------------------

    async def request_closure(
        self,
        *,
        risk_entry_id: uuid.UUID,
        organization_id: uuid.UUID,
        requested_by: uuid.UUID,
        note: str | None,
    ) -> ClosureApproval:
        stmt = select(RiskEntry).where(
            RiskEntry.id == risk_entry_id,
            RiskEntry.organization_id == organization_id,
        )
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("RiskEntry", str(risk_entry_id))
        if entry.risk_level not in (RiskLevel.HIGH, RiskLevel.EXTREME):
            raise RRSyncError("Closure approval is only required for High/Extreme records.")
        approval = ClosureApproval(
            risk_entry_id=risk_entry_id,
            requested_by=requested_by,
            request_note=note,
        )
        self._db.add(approval)
        await self._db.flush()
        logger.info(
            "closure_approval_requested",
            risk_id=str(risk_entry_id),
            risk_level=entry.risk_level.value,
        )
        return approval

    async def decide_closure(
        self,
        *,
        approval_id: uuid.UUID,
        organization_id: uuid.UUID,
        approver_user_id: uuid.UUID,
        approve: bool,
        note: str | None,
    ) -> ClosureApproval:
        stmt = (
            select(ClosureApproval)
            .join(RiskEntry, ClosureApproval.risk_entry_id == RiskEntry.id)
            .where(
                ClosureApproval.id == approval_id,
                RiskEntry.organization_id == organization_id,
            )
        )
        approval = (await self._db.execute(stmt)).scalar_one_or_none()
        if approval is None:
            raise NotFoundError("ClosureApproval", str(approval_id))
        if approval.status != ClosureApprovalStatus.PENDING:
            raise RRSyncError(f"Approval is already {approval.status.value}; cannot re-decide.")
        approval.status = (
            ClosureApprovalStatus.APPROVED if approve else ClosureApprovalStatus.REJECTED
        )
        approval.approver_user_id = approver_user_id
        approval.approval_note = note
        approval.resolved_at = datetime.now(UTC)
        await self._db.flush()
        logger.info(
            "closure_approval_decided",
            approval_id=str(approval_id),
            approved=approve,
        )
        return approval

    async def assert_closure_allowed(self, risk_entry_id: uuid.UUID) -> None:
        """Raise ClosureGateError if a High/Extreme record has no APPROVED approval."""
        stmt = select(RiskEntry).where(RiskEntry.id == risk_entry_id)
        entry = (await self._db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise NotFoundError("RiskEntry", str(risk_entry_id))
        if entry.risk_level not in (RiskLevel.HIGH, RiskLevel.EXTREME):
            return
        approval_stmt = select(ClosureApproval).where(
            ClosureApproval.risk_entry_id == risk_entry_id,
            ClosureApproval.status == ClosureApprovalStatus.APPROVED,
        )
        approved = (await self._db.execute(approval_stmt)).scalar_one_or_none()
        if approved is None:
            raise ClosureGateError(
                "High/Extreme records require Accountable Executive approval before "
                "they can be closed. Request a closure approval first."
            )


def _snapshot_entry(entry: RiskEntry) -> dict[str, Any]:
    """Capture all syncable fields into a JSON-serializable dict."""
    snapshot: dict[str, Any] = {}
    for field in SYNCABLE_FIELDS + ("function_type",):
        value = getattr(entry, field, None)
        if value is None:
            snapshot[field] = None
        elif hasattr(value, "value"):  # enums
            snapshot[field] = value.value
        else:
            snapshot[field] = value
    return snapshot


def compute_entry_diff(before: dict[str, Any], after: RiskEntry) -> dict[str, dict[str, Any]]:
    """Compute the {field: {old, new}} diff between a pre-update snapshot and an entry."""
    diff: dict[str, dict[str, Any]] = {}
    after_snap = _snapshot_entry(after)
    for field in SYNCABLE_FIELDS:
        old = before.get(field)
        new = after_snap.get(field)
        if old != new:
            diff[field] = {"old": old, "new": new}
    return diff
