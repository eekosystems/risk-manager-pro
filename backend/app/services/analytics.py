import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    ActivityEntry,
    DashboardResponse,
    MitigationPerformance,
    RiskKPIs,
    RiskLevelTimeSeries,
    RiskPositionItem,
    RisksByFunctionTypeItem,
    RiskStatusBreakdownItem,
)


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = AnalyticsRepository(db)

    async def get_dashboard(self, organization_id: uuid.UUID) -> DashboardResponse:
        (
            kpi_data,
            time_series_data,
            status_data,
            func_data,
            mit_data,
            position_data,
        ) = await asyncio.gather(
            self._repo.get_kpis(organization_id),
            self._repo.get_risk_level_over_time(organization_id),
            self._repo.get_status_breakdown(organization_id),
            self._repo.get_by_function_type(organization_id),
            self._repo.get_mitigation_performance(organization_id),
            self._repo.get_risk_positions(organization_id),
        )

        return DashboardResponse(
            kpis=RiskKPIs(**kpi_data),
            risk_level_over_time=[RiskLevelTimeSeries(**row) for row in time_series_data],
            status_breakdown=[RiskStatusBreakdownItem(**row) for row in status_data],
            by_function_type=[RisksByFunctionTypeItem(**row) for row in func_data],
            mitigation_performance=MitigationPerformance(**mit_data),
            risk_positions=[RiskPositionItem(**row) for row in position_data],
        )

    async def get_recent_activity(
        self, organization_id: uuid.UUID, limit: int = 20
    ) -> list[ActivityEntry]:
        entries = await self._repo.get_recent_activity(organization_id, limit)
        return [ActivityEntry.model_validate(entry) for entry in entries]
