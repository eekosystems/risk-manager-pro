import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    get_openai_client,
    get_rag_service,
    require_analyst_or_above,
    require_any_member,
)
from app.core.exceptions import ExternalServiceError
from app.models.notification import NotificationType
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse, PaginatedMeta, PaginatedResponse
from app.schemas.risk import (
    CreateMitigationRequest,
    CreateRiskEntryRequest,
    MitigationResponse,
    ResidualAssessmentResponse,
    RiskEntryDetailResponse,
    RiskEntryListItem,
    RiskEntryResponse,
    SrmdImportResult,
    UpdateMitigationRequest,
    UpdateRiskEntryRequest,
)
from app.services.audit import AuditLogger
from app.services.notification import NotificationDispatcher
from app.services.openai_client import AzureOpenAIClient
from app.services.rag import RAGService
from app.services.residual_assessment import ResidualAssessmentRunner, ResidualAssessmentService
from app.services.risk import RiskService
from app.services.risk_outcome_importer import RiskOutcomeImporter
from app.services.risk_threshold import RiskThresholdService
from app.services.srmd_import import SrmdImportService

_notification_dispatcher = NotificationDispatcher()

router = APIRouter(prefix="/risks", tags=["risks"])


def _get_risk_service(db: AsyncSession = Depends(get_db)) -> RiskService:
    return RiskService(db=db)


def _get_residual_assessment_service(
    db: AsyncSession = Depends(get_db),
    openai_client: AzureOpenAIClient = Depends(get_openai_client),
    rag_service: RAGService = Depends(get_rag_service),
) -> ResidualAssessmentService:
    runner = ResidualAssessmentRunner(async_session_factory, openai_client, rag_service)
    return ResidualAssessmentService(db=db, runner=runner)


def _get_srmd_import_service(db: AsyncSession = Depends(get_db)) -> SrmdImportService:
    return SrmdImportService(db=db)


def _get_risk_outcome_importer(request: Request) -> RiskOutcomeImporter:
    try:
        importer: RiskOutcomeImporter = request.app.state.services.risk_outcome_importer
    except RuntimeError as exc:
        raise ExternalServiceError("SharePoint", "the risk-outcome scan is unavailable") from exc
    return importer


async def _request_reassessment(
    risk_id: uuid.UUID,
    trigger: str,
    current_user: User,
    organization: Organization,
    residual_service: ResidualAssessmentService,
    audit: AuditLogger,
) -> ResidualAssessmentResponse:
    assessment = await residual_service.request(
        risk_id, organization.id, current_user.id, trigger=trigger
    )
    await audit.log(
        action="risk.residual_assessment_requested",
        user=current_user,
        resource_type="risk_entry",
        resource_id=str(risk_id),
        organization_id=organization.id,
        metadata={"assessment_id": str(assessment.id), "trigger": trigger},
    )
    return ResidualAssessmentResponse.model_validate(assessment)


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
        # M-8: don't persist hazard content in the notification body — it's
        # readable by any org member. Link to the record instead.
        body=f"{current_user.display_name} created a new risk. Open the record for details.",
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
    limit: int = Query(50, ge=1, le=500),
    status: str | None = Query(None),
    risk_level: str | None = Query(None),
    airport_identifier: str | None = Query(None),
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: RiskService = Depends(_get_risk_service),
    residual_service: ResidualAssessmentService = Depends(_get_residual_assessment_service),
) -> PaginatedResponse[RiskEntryListItem]:
    entries, total = await service.list_risk_entries(
        organization_id=organization.id,
        skip=skip,
        limit=limit,
        status=status,
        risk_level=risk_level,
        airport_identifier=airport_identifier,
    )
    latest = await residual_service.latest_for_entries([e.id for e in entries], organization.id)
    items = [
        RiskEntryListItem.model_validate(e).model_copy(
            update={
                "latest_assessment": (
                    ResidualAssessmentResponse.model_validate(latest[e.id])
                    if e.id in latest
                    else None
                )
            }
        )
        for e in entries
    ]
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


@router.post("/import-srmd", response_model=DataResponse[SrmdImportResult], status_code=201)
async def import_srmd_hazards(
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    importer: RiskOutcomeImporter = Depends(_get_risk_outcome_importer),
    service: SrmdImportService = Depends(_get_srmd_import_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[SrmdImportResult]:
    summary = await importer.snapshot()
    created, already_imported = await service.import_hazards(
        summary.risks, organization, current_user.id
    )
    for entry in created:
        await audit.log(
            action="risk.created",
            user=current_user,
            resource_type="risk_entry",
            resource_id=str(entry.id),
            organization_id=organization.id,
            metadata={"source": "sharepoint_srmd"},
        )
    await audit.log(
        action="risk.srmd_imported",
        user=current_user,
        resource_type="risk_register",
        resource_id=str(organization.id),
        organization_id=organization.id,
        metadata={"imported": len(created), "already_imported": already_imported},
    )
    result = SrmdImportResult(
        imported=len(created),
        already_imported=already_imported,
        risk_ids=[e.id for e in created],
    )
    return DataResponse(data=result, meta=MetaResponse(request_id=str(organization.id)))


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
    residual_service: ResidualAssessmentService = Depends(_get_residual_assessment_service),
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
    await _request_reassessment(
        risk_id, "mitigation.created", current_user, organization, residual_service, audit
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
    residual_service: ResidualAssessmentService = Depends(_get_residual_assessment_service),
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
    await _request_reassessment(
        risk_id, "mitigation.updated", current_user, organization, residual_service, audit
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
    residual_service: ResidualAssessmentService = Depends(_get_residual_assessment_service),
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
    await _request_reassessment(
        risk_id, "mitigation.deleted", current_user, organization, residual_service, audit
    )


# --- Residual Re-assessment Endpoints ---


@router.post(
    "/{risk_id}/residual-assessments",
    response_model=DataResponse[ResidualAssessmentResponse],
    status_code=202,
)
async def request_residual_assessment(
    risk_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    residual_service: ResidualAssessmentService = Depends(_get_residual_assessment_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[ResidualAssessmentResponse]:
    assessment = await _request_reassessment(
        risk_id, "manual", current_user, organization, residual_service, audit
    )
    return DataResponse(data=assessment, meta=MetaResponse(request_id=str(assessment.id)))


@router.post(
    "/{risk_id}/residual-assessments/{assessment_id}/confirm",
    response_model=DataResponse[ResidualAssessmentResponse],
)
async def confirm_residual_assessment(
    risk_id: uuid.UUID,
    assessment_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    residual_service: ResidualAssessmentService = Depends(_get_residual_assessment_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[ResidualAssessmentResponse]:
    assessment = await residual_service.confirm(
        risk_id, assessment_id, organization.id, current_user.id
    )
    await audit.log(
        action="risk.residual_confirmed",
        user=current_user,
        resource_type="risk_entry",
        resource_id=str(risk_id),
        organization_id=organization.id,
        metadata={
            "assessment_id": str(assessment_id),
            "residual_likelihood": assessment.residual_likelihood,
            "residual_severity": assessment.residual_severity,
        },
    )
    return DataResponse(
        data=ResidualAssessmentResponse.model_validate(assessment),
        meta=MetaResponse(request_id=str(assessment_id)),
    )


@router.post(
    "/{risk_id}/residual-assessments/{assessment_id}/dismiss",
    response_model=DataResponse[ResidualAssessmentResponse],
)
async def dismiss_residual_assessment(
    risk_id: uuid.UUID,
    assessment_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    residual_service: ResidualAssessmentService = Depends(_get_residual_assessment_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[ResidualAssessmentResponse]:
    assessment = await residual_service.dismiss(
        risk_id, assessment_id, organization.id, current_user.id
    )
    await audit.log(
        action="risk.residual_dismissed",
        user=current_user,
        resource_type="risk_entry",
        resource_id=str(risk_id),
        organization_id=organization.id,
        metadata={"assessment_id": str(assessment_id)},
    )
    return DataResponse(
        data=ResidualAssessmentResponse.model_validate(assessment),
        meta=MetaResponse(request_id=str(assessment_id)),
    )
