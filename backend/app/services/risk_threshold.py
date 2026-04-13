"""Evaluate per-org risk thresholds and dispatch alerts when breached."""

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationType
from app.models.risk import RiskEntry, RiskLevel, RiskStatus
from app.models.risk_threshold import RiskAlertThreshold
from app.models.user import User
from app.services.notification import NotificationDispatcher

logger = structlog.get_logger(__name__)


class RiskThresholdService:
    def __init__(self, db: AsyncSession, dispatcher: NotificationDispatcher) -> None:
        self._db = db
        self._dispatcher = dispatcher

    async def evaluate(
        self,
        organization_id: uuid.UUID,
        triggered_by: User,
        risk_level: RiskLevel,
    ) -> None:
        threshold_stmt = select(RiskAlertThreshold).where(
            RiskAlertThreshold.organization_id == organization_id,
            RiskAlertThreshold.risk_level == risk_level.value,
        )
        threshold = (await self._db.execute(threshold_stmt)).scalar_one_or_none()
        if threshold is None:
            return

        count_stmt = select(func.count()).select_from(
            select(RiskEntry.id)
            .where(
                RiskEntry.organization_id == organization_id,
                RiskEntry.risk_level == risk_level,
                RiskEntry.status.in_((RiskStatus.OPEN, RiskStatus.MITIGATING)),
            )
            .subquery()
        )
        open_count = (await self._db.execute(count_stmt)).scalar_one()

        if open_count <= threshold.max_open_count:
            return

        logger.warning(
            "risk_threshold_exceeded",
            organization_id=str(organization_id),
            risk_level=risk_level.value,
            open_count=open_count,
            threshold=threshold.max_open_count,
        )

        self._dispatcher.dispatch(
            organization_id=organization_id,
            triggered_by=triggered_by,
            notification_type=NotificationType.RISK_THRESHOLD_EXCEEDED,
            title=f"Risk threshold exceeded: {open_count} open {risk_level.value} risks",
            body=(
                f"Organization has {open_count} open {risk_level.value}-level "
                f"risks; threshold is {threshold.max_open_count}."
            ),
            resource_type="risk_threshold",
            resource_id=str(threshold.id),
        )
