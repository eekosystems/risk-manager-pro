import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_audit_logger, get_current_organization, get_current_user
from app.core.deps.organization import require_org_role
from app.models.organization import Organization
from app.models.organization_membership import MembershipRole
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse
from app.schemas.settings import (
    ModelPreferencesPayload,
    PromptsPayload,
    QaqcSettingsPayload,
    RagSettingsPayload,
    SettingsResponse,
)
from app.services.audit import AuditLogger
from app.services.settings import SettingsService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    return SettingsService(db=db)


# ── Read ──────────────────────────────────────────────────────────────


@router.get("", response_model=DataResponse[list[SettingsResponse]])
async def get_all_settings(
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: SettingsService = Depends(_get_settings_service),
) -> DataResponse[list[SettingsResponse]]:
    """Get all settings for the current organization."""
    result = await service.get_all_settings(organization.id)
    return DataResponse(
        data=result,
        meta=MetaResponse(request_id=""),
    )


@router.get("/{category}", response_model=DataResponse[SettingsResponse])
async def get_settings_by_category(
    category: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: SettingsService = Depends(_get_settings_service),
) -> DataResponse[SettingsResponse]:
    """Get settings for a specific category (rag, model, prompts)."""
    result = await service.get_settings(organization.id, category)
    return DataResponse(
        data=result,
        meta=MetaResponse(request_id=""),
    )


# ── Write (admin only) ───────────────────────────────────────────────


@router.put(
    "/rag",
    response_model=DataResponse[SettingsResponse],
    dependencies=[Depends(require_org_role(MembershipRole.ORG_ADMIN))],
)
async def update_rag_settings(
    payload: RagSettingsPayload,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: SettingsService = Depends(_get_settings_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[SettingsResponse]:
    """Update RAG pipeline settings. Requires org_admin role."""
    result = await service.update_rag_settings(organization.id, payload, current_user.id)
    await audit.log(
        action="settings.rag.updated",
        user=current_user,
        resource_type="settings",
        resource_id="rag",
        organization_id=organization.id,
    )
    return DataResponse(data=result, meta=MetaResponse(request_id=""))


@router.put(
    "/model",
    response_model=DataResponse[SettingsResponse],
    dependencies=[Depends(require_org_role(MembershipRole.ORG_ADMIN))],
)
async def update_model_settings(
    payload: ModelPreferencesPayload,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: SettingsService = Depends(_get_settings_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[SettingsResponse]:
    """Update AI model preferences. Requires org_admin role."""
    result = await service.update_model_settings(organization.id, payload, current_user.id)
    await audit.log(
        action="settings.model.updated",
        user=current_user,
        resource_type="settings",
        resource_id="model",
        organization_id=organization.id,
    )
    return DataResponse(data=result, meta=MetaResponse(request_id=""))


@router.put(
    "/prompts",
    response_model=DataResponse[SettingsResponse],
    dependencies=[Depends(require_org_role(MembershipRole.ORG_ADMIN))],
)
async def update_prompts(
    payload: PromptsPayload,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: SettingsService = Depends(_get_settings_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[SettingsResponse]:
    """Update system and function-specific prompts. Requires org_admin role."""
    result = await service.update_prompts(organization.id, payload, current_user.id)
    await audit.log(
        action="settings.prompts.updated",
        user=current_user,
        resource_type="settings",
        resource_id="prompts",
        organization_id=organization.id,
    )
    return DataResponse(data=result, meta=MetaResponse(request_id=""))


@router.put(
    "/qaqc",
    response_model=DataResponse[SettingsResponse],
    dependencies=[Depends(require_org_role(MembershipRole.ORG_ADMIN))],
)
async def update_qaqc_settings(
    payload: QaqcSettingsPayload,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: SettingsService = Depends(_get_settings_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[SettingsResponse]:
    """Update QA/QC reviewer settings. Requires org_admin role."""
    result = await service.update_qaqc_settings(organization.id, payload, current_user.id)
    await audit.log(
        action="settings.qaqc.updated",
        user=current_user,
        resource_type="settings",
        resource_id="qaqc",
        organization_id=organization.id,
    )
    return DataResponse(data=result, meta=MetaResponse(request_id=""))
