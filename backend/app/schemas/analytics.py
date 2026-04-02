import uuid
from datetime import datetime

from pydantic import BaseModel


class RiskKPIs(BaseModel):
    total_risks: int
    open_risks: int
    high_count: int
    overdue_mitigations: int
    avg_days_to_close: float | None


class RiskLevelTimeSeries(BaseModel):
    month: str
    low: int
    medium: int
    high: int


class RiskStatusBreakdownItem(BaseModel):
    status: str
    count: int


class RisksByFunctionTypeItem(BaseModel):
    function_type: str
    count: int


class MitigationPerformance(BaseModel):
    total_mitigations: int
    completed_count: int
    overdue_count: int
    completion_rate: float
    avg_days_to_complete: float | None


class RiskPositionItem(BaseModel):
    likelihood: str
    severity: int
    count: int


class DashboardResponse(BaseModel):
    kpis: RiskKPIs
    risk_level_over_time: list[RiskLevelTimeSeries]
    status_breakdown: list[RiskStatusBreakdownItem]
    by_function_type: list[RisksByFunctionTypeItem]
    mitigation_performance: MitigationPerformance
    risk_positions: list[RiskPositionItem]


class ActivityEntry(BaseModel):
    id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    timestamp: datetime
    user_id: uuid.UUID

    model_config = {"from_attributes": True}
