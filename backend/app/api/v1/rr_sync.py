"""API endpoints for dual RR sync, ACP, closure approvals, and portfolio view."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    require_analyst_or_above,
    require_any_member,
    require_platform_admin,
)
from app.models.organization import Organization
from app.models.risk import RiskEntry
from app.models.rr_sync import ACPDecision, PendingChangeStatus
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse
from app.schemas.rr_sync import (
    ACPIntelligenceItemResponse,
    ACPItemDecisionRequest,
    ACPResponse,
    ClosureApprovalResponse,
    ClosureDecisionRequest,
    CreateACPIntelligenceItemRequest,
    PendingSyncChangeResponse,
    PortfolioRiskRow,
    RequestClosureRequest,
    ReviewDecisionRequest,
    UpdateACPRequest,
)
from app.services.audit import AuditLogger
from app.services.rr_sync import RRSyncService

router = APIRouter(prefix="/rr", tags=["risk-register-sync"])


def _get_sync_service(db: AsyncSession = Depends(get_db)) -> RRSyncService:
    return RRSyncService(db=db)


# --------------------------------------------------------------------
# Pending sync review queue
# --------------------------------------------------------------------


@router.get(
    "/sync-queue",
    response_model=DataResponse[list[PendingSyncChangeResponse]],
)
async def list_pending_changes(
    status: PendingChangeStatus | None = Query(default=PendingChangeStatus.PENDING),
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: RRSyncService = Depends(_get_sync_service),
) -> DataResponse[list[PendingSyncChangeResponse]]:
    items = await service.list_pending_changes(organization_id=organization.id, status=status)
    return DataResponse(
        data=[PendingSyncChangeResponse.model_validate(i) for i in items],
        meta=MetaResponse(request_id=str(organization.id)),
    )


@router.post(
    "/sync-queue/{pending_id}/accept",
    response_model=DataResponse[PendingSyncChangeResponse],
)
async def accept_pending_change(
    pending_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RRSyncService = Depends(_get_sync_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[PendingSyncChangeResponse]:
    row = await service.accept_pending_change(
        pending_id=pending_id,
        reviewer_user_id=current_user.id,
        reviewer_org_id=organization.id,
        note=payload.note,
    )
    await audit.log(
        action="rr.sync.accepted",
        user=current_user,
        resource_type="pending_sync_change",
        resource_id=str(pending_id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=PendingSyncChangeResponse.model_validate(row),
        meta=MetaResponse(request_id=str(pending_id)),
    )


@router.post(
    "/sync-queue/{pending_id}/reject",
    response_model=DataResponse[PendingSyncChangeResponse],
)
async def reject_pending_change(
    pending_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RRSyncService = Depends(_get_sync_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[PendingSyncChangeResponse]:
    row = await service.reject_pending_change(
        pending_id=pending_id,
        reviewer_user_id=current_user.id,
        reviewer_org_id=organization.id,
        note=payload.note,
    )
    await audit.log(
        action="rr.sync.rejected",
        user=current_user,
        resource_type="pending_sync_change",
        resource_id=str(pending_id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=PendingSyncChangeResponse.model_validate(row),
        meta=MetaResponse(request_id=str(pending_id)),
    )


# --------------------------------------------------------------------
# Airport Context Profile (FG-scoped, platform org only)
# --------------------------------------------------------------------


@router.get(
    "/acp/{airport_identifier}",
    response_model=DataResponse[ACPResponse],
)
async def get_acp(
    airport_identifier: str,
    current_user: User = Depends(require_platform_admin),
    service: RRSyncService = Depends(_get_sync_service),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[ACPResponse]:
    platform_org_id = await _resolve_platform_org_id(db)
    acp = await service.get_or_create_acp(platform_org_id, airport_identifier)
    return DataResponse(
        data=ACPResponse.model_validate(acp),
        meta=MetaResponse(request_id=str(acp.id)),
    )


@router.patch(
    "/acp/{acp_id}",
    response_model=DataResponse[ACPResponse],
)
async def update_acp(
    acp_id: uuid.UUID,
    payload: UpdateACPRequest,
    current_user: User = Depends(require_platform_admin),
    service: RRSyncService = Depends(_get_sync_service),
    audit: AuditLogger = Depends(get_audit_logger),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[ACPResponse]:
    platform_org_id = await _resolve_platform_org_id(db)
    acp = await service.update_acp(
        acp_id=acp_id,
        organization_id=platform_org_id,
        **payload.model_dump(exclude_unset=True),
    )
    await audit.log(
        action="acp.updated",
        user=current_user,
        resource_type="airport_context_profile",
        resource_id=str(acp_id),
        organization_id=platform_org_id,
    )
    return DataResponse(
        data=ACPResponse.model_validate(acp),
        meta=MetaResponse(request_id=str(acp_id)),
    )


@router.post(
    "/acp/intelligence",
    response_model=DataResponse[ACPIntelligenceItemResponse],
    status_code=201,
)
async def create_intelligence_item(
    payload: CreateACPIntelligenceItemRequest,
    current_user: User = Depends(require_platform_admin),
    service: RRSyncService = Depends(_get_sync_service),
    audit: AuditLogger = Depends(get_audit_logger),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[ACPIntelligenceItemResponse]:
    platform_org_id = await _resolve_platform_org_id(db)
    item = await service.add_intelligence_item(
        organization_id=platform_org_id,
        airport_identifier=payload.airport_identifier,
        source=payload.source.value,
        headline=payload.headline,
        summary=payload.summary,
        occurred_at=payload.occurred_at,
        external_url=payload.external_url,
        external_ref=payload.external_ref,
        raw_payload=payload.raw_payload,
        created_by=current_user.id,
    )
    await audit.log(
        action="acp.intelligence.created",
        user=current_user,
        resource_type="acp_intelligence",
        resource_id=str(item.id),
        organization_id=platform_org_id,
    )
    return DataResponse(
        data=ACPIntelligenceItemResponse.model_validate(item),
        meta=MetaResponse(request_id=str(item.id)),
    )


@router.get(
    "/acp/intelligence",
    response_model=DataResponse[list[ACPIntelligenceItemResponse]],
)
async def list_intelligence_items(
    airport_identifier: str | None = Query(default=None),
    decision: ACPDecision | None = Query(default=None),
    current_user: User = Depends(require_platform_admin),
    service: RRSyncService = Depends(_get_sync_service),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[list[ACPIntelligenceItemResponse]]:
    platform_org_id = await _resolve_platform_org_id(db)
    items = await service.list_intelligence_items(
        organization_id=platform_org_id,
        airport_identifier=airport_identifier,
        decision=decision,
    )
    return DataResponse(
        data=[ACPIntelligenceItemResponse.model_validate(i) for i in items],
        meta=MetaResponse(request_id=str(platform_org_id)),
    )


@router.post(
    "/acp/intelligence/{item_id}/decide",
    response_model=DataResponse[ACPIntelligenceItemResponse],
)
async def decide_intelligence_item(
    item_id: uuid.UUID,
    payload: ACPItemDecisionRequest,
    current_user: User = Depends(require_platform_admin),
    service: RRSyncService = Depends(_get_sync_service),
    audit: AuditLogger = Depends(get_audit_logger),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[ACPIntelligenceItemResponse]:
    platform_org_id = await _resolve_platform_org_id(db)
    item = await service.decide_intelligence_item(
        item_id=item_id,
        organization_id=platform_org_id,
        decision=payload.decision,
        decided_by=current_user.id,
        note=payload.note,
        linked_risk_entry_id=payload.linked_risk_entry_id,
    )
    await audit.log(
        action="acp.intelligence.decided",
        user=current_user,
        resource_type="acp_intelligence",
        resource_id=str(item_id),
        organization_id=platform_org_id,
    )
    return DataResponse(
        data=ACPIntelligenceItemResponse.model_validate(item),
        meta=MetaResponse(request_id=str(item_id)),
    )


# --------------------------------------------------------------------
# Closure approvals
# --------------------------------------------------------------------


@router.post(
    "/closures/{risk_id}/request",
    response_model=DataResponse[ClosureApprovalResponse],
    status_code=201,
)
async def request_closure_approval(
    risk_id: uuid.UUID,
    payload: RequestClosureRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RRSyncService = Depends(_get_sync_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[ClosureApprovalResponse]:
    approval = await service.request_closure(
        risk_entry_id=risk_id,
        organization_id=organization.id,
        requested_by=current_user.id,
        note=payload.note,
    )
    await audit.log(
        action="closure.requested",
        user=current_user,
        resource_type="closure_approval",
        resource_id=str(approval.id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=ClosureApprovalResponse.model_validate(approval),
        meta=MetaResponse(request_id=str(approval.id)),
    )


@router.post(
    "/closures/{approval_id}/decide",
    response_model=DataResponse[ClosureApprovalResponse],
)
async def decide_closure_approval(
    approval_id: uuid.UUID,
    payload: ClosureDecisionRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RRSyncService = Depends(_get_sync_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[ClosureApprovalResponse]:
    approval = await service.decide_closure(
        approval_id=approval_id,
        organization_id=organization.id,
        approver_user_id=current_user.id,
        approve=payload.approve,
        note=payload.note,
    )
    await audit.log(
        action="closure.decided",
        user=current_user,
        resource_type="closure_approval",
        resource_id=str(approval_id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=ClosureApprovalResponse.model_validate(approval),
        meta=MetaResponse(request_id=str(approval_id)),
    )


# --------------------------------------------------------------------
# Portfolio view (platform-admin only, cross-org)
# --------------------------------------------------------------------


@router.get(
    "/portfolio",
    response_model=DataResponse[list[PortfolioRiskRow]],
)
async def portfolio_view(
    airport_identifier: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[list[PortfolioRiskRow]]:
    """Cross-organization risk roll-up. Platform admins only.

    Joins every risk_entries row to its owning organization and returns a
    flat list suitable for a portfolio table view in the UI. Filter by
    airport identifier (exact match) and/or risk level.
    """
    stmt = (
        select(RiskEntry, Organization.name)
        .join(Organization, RiskEntry.organization_id == Organization.id)
        .order_by(RiskEntry.updated_at.desc())
        .limit(limit)
    )
    if airport_identifier:
        stmt = stmt.where(RiskEntry.airport_identifier == airport_identifier)
    if risk_level:
        stmt = stmt.where(RiskEntry.risk_level == risk_level)

    result = await db.execute(stmt)
    rows: list[PortfolioRiskRow] = []
    for entry, org_name in result.all():
        rows.append(
            PortfolioRiskRow(
                id=entry.id,
                organization_id=entry.organization_id,
                organization_name=org_name,
                airport_identifier=entry.airport_identifier,
                title=entry.title,
                hazard=entry.hazard,
                severity=int(entry.severity),
                likelihood=entry.likelihood,
                risk_level=entry.risk_level.value,
                record_status=entry.record_status.value,
                validation_status=entry.validation_status.value,
                source=entry.source.value,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
        )
    return DataResponse(data=rows, meta=MetaResponse(request_id="portfolio"))


async def _resolve_platform_org_id(db: AsyncSession) -> uuid.UUID:
    """Return the Faith Group platform organization id, or 400 if not configured."""
    stmt = select(Organization.id).where(Organization.is_platform.is_(True)).limit(1)
    org_id = (await db.execute(stmt)).scalar_one_or_none()
    if org_id is None:
        from app.core.exceptions import AppError

        raise AppError(
            code="PLATFORM_ORG_NOT_CONFIGURED",
            message=(
                "No platform organization exists. ACP and portfolio views require "
                "a Faith Group org with is_platform=true."
            ),
            status_code=500,
        )
    return org_id
