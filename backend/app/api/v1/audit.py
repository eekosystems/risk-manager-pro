import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_organization, get_current_user, require_org_role
from app.models.organization import Organization
from app.models.organization_membership import MembershipRole
from app.models.user import User
from app.schemas.audit import AuditEntryResponse
from app.schemas.common import DataResponse, MetaResponse, PaginatedMeta, PaginatedResponse
from app.services.audit_query import AuditQueryService

router = APIRouter(prefix="/audit", tags=["audit"])


def _get_audit_query_service(db: AsyncSession = Depends(get_db)) -> AuditQueryService:
    return AuditQueryService(db=db)


@router.get("", response_model=PaginatedResponse[AuditEntryResponse])
async def list_audit_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    outcome: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    organization: Organization = Depends(get_current_organization),
    service: AuditQueryService = Depends(_get_audit_query_service),
) -> PaginatedResponse[AuditEntryResponse]:
    entries, total = await service.list_entries(
        organization_id=organization.id,
        skip=skip,
        limit=limit,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
    )
    total_pages = (total + limit - 1) // limit
    return PaginatedResponse(
        data=entries,
        meta=PaginatedMeta(
            request_id="",
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
            total_pages=total_pages,
        ),
    )


@router.get("/filters", response_model=DataResponse[dict[str, list[str]]])
async def get_audit_filter_options(
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    organization: Organization = Depends(get_current_organization),
    service: AuditQueryService = Depends(_get_audit_query_service),
) -> DataResponse[dict[str, list[str]]]:
    options = await service.get_filter_options(organization.id)
    return DataResponse(data=options, meta=MetaResponse(request_id=""))


@router.get("/export")
async def export_audit_csv(
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    outcome: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: User = Depends(require_org_role(MembershipRole.ORG_ADMIN)),
    organization: Organization = Depends(get_current_organization),
    service: AuditQueryService = Depends(_get_audit_query_service),
) -> StreamingResponse:
    csv_content = await service.export_csv(
        organization_id=organization.id,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
    )
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
