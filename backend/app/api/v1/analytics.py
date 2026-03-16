from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_organization, get_current_user
from app.models.organization import Organization
from app.models.user import User
from app.schemas.analytics import ActivityEntry, DashboardResponse
from app.schemas.common import DataResponse, MetaResponse
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db=db)


@router.get("/dashboard", response_model=DataResponse[DashboardResponse])
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> DataResponse[DashboardResponse]:
    result = await service.get_dashboard(organization.id)
    return DataResponse(data=result, meta=MetaResponse(request_id=""))


@router.get("/activity", response_model=DataResponse[list[ActivityEntry]])
async def get_recent_activity(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: AnalyticsService = Depends(_get_analytics_service),
) -> DataResponse[list[ActivityEntry]]:
    entries = await service.get_recent_activity(organization.id, limit)
    return DataResponse(data=entries, meta=MetaResponse(request_id=""))
