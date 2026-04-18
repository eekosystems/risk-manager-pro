import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    require_analyst_or_above,
    require_any_member,
)
from app.models.notification import NotificationType
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse, PaginatedMeta, PaginatedResponse
from app.schemas.risk import (
    CreateMitigationRequest,
    CreateRiskEntryRequest,
    MitigationResponse,
    RiskEntryDetailResponse,
    RiskEntryListItem,
    RiskEntryResponse,
    UpdateMitigationRequest,
    UpdateRiskEntryRequest,
)
from app.services.audit import AuditLogger
from app.services.notification import NotificationDispatcher
from app.services.risk import RiskService
from app.services.risk_threshold import RiskThresholdService

_notification_dispatcher = NotificationDispatcher()

router = APIRouter(prefix="/risks", tags=["risks"])


def _get_risk_service(db: AsyncSession = Depends(get_db)) -> RiskService:
    return RiskService(db=db)


def _get_threshold_service(
    db: AsyncSession = Depends(get_db),
) -> RiskThresholdService:
    return RiskThresholdService(db=db, dispatcher=_notification_dispatcher)


# --- Risk Entry Endpoints ---


@router.post("", response_model=DataResponse[RiskEntryResponse], status_code=201)
async def create_risk_entry(
    payload: CreateRiskEntryRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
    threshold_service: RiskThresholdService = Depends(_get_threshold_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[RiskEntryResponse]:
    entry = await service.create_risk_entry(payload, current_user.id, organization.id)
    await threshold_service.evaluate(organization.id, current_user, entry.risk_level)
    await audit.log(
        action="risk.created",
        user=current_user,
        resource_type="risk_entry",
        resource_id=str(entry.id),
        organization_id=organization.id,
    )
    _notification_dispatcher.dispatch(
        organization_id=organization.id,
        triggered_by=current_user,
        notification_type=NotificationType.RISK_CREATED,
        title=f"New risk: {payload.title[:100]}",
        body=f"Hazard: {payload.hazard[:200]} | Severity: {payload.severity}, Likelihood: {payload.likelihood}",
        resource_type="risk_entry",
        resource_id=str(entry.id),
    )
    return DataResponse(
        data=RiskEntryResponse.model_validate(entry),
        meta=MetaResponse(request_id=str(entry.id)),
    )


@router.get("", response_model=PaginatedResponse[RiskEntryListItem])
async def list_risk_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = Query(None),
    risk_level: str | None = Query(None),
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
) -> PaginatedResponse[RiskEntryListItem]:
    entries, total = await service.list_risk_entries(
        organization_id=organization.id,
        skip=skip,
        limit=limit,
        status=status,
        risk_level=risk_level,
    )
    items = [RiskEntryListItem.model_validate(e) for e in entries]
    total_pages = (total + limit - 1) // limit
    return PaginatedResponse(
        data=items,
        meta=PaginatedMeta(
            request_id="",
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
            total_pages=total_pages,
        ),
    )


@router.get("/{risk_id}", response_model=DataResponse[RiskEntryDetailResponse])
async def get_risk_entry(
    risk_id: uuid.UUID,
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
) -> DataResponse[RiskEntryDetailResponse]:
    entry = await service.get_risk_entry(risk_id, organization.id)
    return DataResponse(
        data=RiskEntryDetailResponse.model_validate(entry),
        meta=MetaResponse(request_id=str(risk_id)),
    )


@router.patch("/{risk_id}", response_model=DataResponse[RiskEntryResponse])
async def update_risk_entry(
    risk_id: uuid.UUID,
    payload: UpdateRiskEntryRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
    threshold_service: RiskThresholdService = Depends(_get_threshold_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[RiskEntryResponse]:
    entry = await service.update_risk_entry(
        risk_id, organization.id, payload, user_id=current_user.id
    )
    await threshold_service.evaluate(organization.id, current_user, entry.risk_level)
    await audit.log(
        action="risk.updated",
        user=current_user,
        resource_type="risk_entry",
        resource_id=str(risk_id),
        organization_id=organization.id,
    )
    changes = payload.model_dump(exclude_unset=True)
    change_summary = (
        ", ".join(f"{k}={v}" for k, v in changes.items() if v is not None) or "(no fields)"
    )
    _notification_dispatcher.dispatch(
        organization_id=organization.id,
        triggered_by=current_user,
        notification_type=NotificationType.RISK_UPDATED,
        title=f"Risk updated: {entry.title[:100]}",
        body=f"Changes: {change_summary}",
        resource_type="risk_entry",
        resource_id=str(risk_id),
    )
    return DataResponse(
        data=RiskEntryResponse.model_validate(entry),
        meta=MetaResponse(request_id=str(risk_id)),
    )


@router.delete("/{risk_id}", status_code=204)
async def delete_risk_entry(
    risk_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    await service.delete_risk_entry(risk_id, organization.id)
    await audit.log(
        action="risk.deleted",
        user=current_user,
        resource_type="risk_entry",
        resource_id=str(risk_id),
        organization_id=organization.id,
    )


# --- Mitigation Endpoints ---


@router.post(
    "/{risk_id}/mitigations",
    response_model=DataResponse[MitigationResponse],
    status_code=201,
)
async def create_mitigation(
    risk_id: uuid.UUID,
    payload: CreateMitigationRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[MitigationResponse]:
    mitigation = await service.create_mitigation(risk_id, organization.id, payload)
    await audit.log(
        action="mitigation.created",
        user=current_user,
        resource_type="mitigation",
        resource_id=str(mitigation.id),
        organization_id=organization.id,
    )
    _notification_dispatcher.dispatch(
        organization_id=organization.id,
        triggered_by=current_user,
        notification_type=NotificationType.MITIGATION_CREATED,
        title=f"New mitigation: {payload.title[:100]}",
        body=f"Risk: {risk_id} | Assignee: {payload.assignee or 'unassigned'} | Due: {payload.due_date or 'not set'}",
        resource_type="mitigation",
        resource_id=str(mitigation.id),
    )
    return DataResponse(
        data=MitigationResponse.model_validate(mitigation),
        meta=MetaResponse(request_id=str(mitigation.id)),
    )


@router.get("/{risk_id}/mitigations", response_model=DataResponse[list[MitigationResponse]])
async def list_mitigations(
    risk_id: uuid.UUID,
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
) -> DataResponse[list[MitigationResponse]]:
    # Verify risk belongs to org
    await service.get_risk_entry(risk_id, organization.id)
    mitigations = await service._repo.list_mitigations(risk_id)
    return DataResponse(
        data=[MitigationResponse.model_validate(m) for m in mitigations],
        meta=MetaResponse(request_id=str(risk_id)),
    )


@router.patch(
    "/{risk_id}/mitigations/{mitigation_id}",
    response_model=DataResponse[MitigationResponse],
)
async def update_mitigation(
    risk_id: uuid.UUID,
    mitigation_id: uuid.UUID,
    payload: UpdateMitigationRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[MitigationResponse]:
    mitigation = await service.update_mitigation(risk_id, mitigation_id, organization.id, payload)
    await audit.log(
        action="mitigation.updated",
        user=current_user,
        resource_type="mitigation",
        resource_id=str(mitigation_id),
        organization_id=organization.id,
    )
    return DataResponse(
        data=MitigationResponse.model_validate(mitigation),
        meta=MetaResponse(request_id=str(mitigation_id)),
    )


@router.delete("/{risk_id}/mitigations/{mitigation_id}", status_code=204)
async def delete_mitigation(
    risk_id: uuid.UUID,
    mitigation_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    await service.delete_mitigation(risk_id, mitigation_id, organization.id)
    await audit.log(
        action="mitigation.deleted",
        user=current_user,
        resource_type="mitigation",
        resource_id=str(mitigation_id),
        organization_id=organization.id,
    )
