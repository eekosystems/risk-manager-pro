import uuid
from datetime import datetime, timezone

from sqlalchemy import case, extract, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEntry
from app.models.risk import Mitigation, MitigationStatus, RiskEntry, RiskStatus


class AnalyticsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_kpis(
        self, organization_id: uuid.UUID
    ) -> dict[str, int | float | None]:
        stmt = (
            select(
                func.count().label("total_risks"),
                func.count().filter(RiskEntry.status == RiskStatus.OPEN).label("open_risks"),
                func.count().filter(RiskEntry.risk_level == "high").label("high_count"),
                func.count().filter(RiskEntry.risk_level == "serious").label("serious_count"),
                func.avg(
                    case(
                        (
                            RiskEntry.status == RiskStatus.CLOSED,
                            extract("epoch", RiskEntry.updated_at - RiskEntry.created_at) / 86400,
                        ),
                    )
                ).label("avg_days_to_close"),
            )
            .where(RiskEntry.organization_id == organization_id)
        )
        result = await self._db.execute(stmt)
        row = result.one()

        # Overdue mitigations: separate query joining to risk_entries for org scoping
        overdue_stmt = (
            select(func.count())
            .select_from(Mitigation)
            .join(RiskEntry, Mitigation.risk_entry_id == RiskEntry.id)
            .where(
                RiskEntry.organization_id == organization_id,
                Mitigation.due_date < func.now(),
                Mitigation.status.notin_([MitigationStatus.COMPLETED, MitigationStatus.CANCELLED]),
            )
        )
        overdue_result = await self._db.execute(overdue_stmt)
        overdue_count = overdue_result.scalar_one()

        avg_close = row.avg_days_to_close
        return {
            "total_risks": row.total_risks,
            "open_risks": row.open_risks,
            "high_count": row.high_count,
            "serious_count": row.serious_count,
            "overdue_mitigations": overdue_count,
            "avg_days_to_close": round(float(avg_close), 1) if avg_close is not None else None,
        }

    async def get_risk_level_over_time(
        self, organization_id: uuid.UUID
    ) -> list[dict[str, str | int]]:
        stmt = (
            select(
                func.to_char(func.date_trunc("month", RiskEntry.created_at), "YYYY-MM").label("month"),
                RiskEntry.risk_level,
                func.count().label("cnt"),
            )
            .where(RiskEntry.organization_id == organization_id)
            .group_by(text("1"), RiskEntry.risk_level)
            .order_by(text("1"))
        )
        result = await self._db.execute(stmt)
        rows = result.all()

        # Pivot into {month: {low: n, medium: n, ...}} structure
        months: dict[str, dict[str, int]] = {}
        for row in rows:
            m = row.month
            if m not in months:
                months[m] = {"low": 0, "medium": 0, "serious": 0, "high": 0}
            months[m][row.risk_level] = row.cnt

        return [{"month": m, **counts} for m, counts in months.items()]

    async def get_status_breakdown(
        self, organization_id: uuid.UUID
    ) -> list[dict[str, str | int]]:
        stmt = (
            select(RiskEntry.status, func.count().label("count"))
            .where(RiskEntry.organization_id == organization_id)
            .group_by(RiskEntry.status)
        )
        result = await self._db.execute(stmt)
        return [{"status": row.status, "count": row.count} for row in result.all()]

    async def get_by_function_type(
        self, organization_id: uuid.UUID
    ) -> list[dict[str, str | int]]:
        stmt = (
            select(RiskEntry.function_type, func.count().label("count"))
            .where(RiskEntry.organization_id == organization_id)
            .group_by(RiskEntry.function_type)
        )
        result = await self._db.execute(stmt)
        return [{"function_type": row.function_type, "count": row.count} for row in result.all()]

    async def get_mitigation_performance(
        self, organization_id: uuid.UUID
    ) -> dict[str, int | float | None]:
        stmt = (
            select(
                func.count().label("total"),
                func.count().filter(Mitigation.status == MitigationStatus.COMPLETED).label("completed"),
                func.count().filter(
                    Mitigation.due_date < func.now(),
                    Mitigation.status.notin_([MitigationStatus.COMPLETED, MitigationStatus.CANCELLED]),
                ).label("overdue"),
                func.avg(
                    case(
                        (
                            Mitigation.status == MitigationStatus.COMPLETED,
                            extract("epoch", Mitigation.completed_at - Mitigation.created_at) / 86400,
                        ),
                    )
                ).label("avg_days"),
            )
            .select_from(Mitigation)
            .join(RiskEntry, Mitigation.risk_entry_id == RiskEntry.id)
            .where(RiskEntry.organization_id == organization_id)
        )
        result = await self._db.execute(stmt)
        row = result.one()

        total = row.total
        completed = row.completed
        return {
            "total_mitigations": total,
            "completed_count": completed,
            "overdue_count": row.overdue,
            "completion_rate": round(completed / total, 3) if total > 0 else 0.0,
            "avg_days_to_complete": round(float(row.avg_days), 1) if row.avg_days is not None else None,
        }

    async def get_risk_positions(
        self, organization_id: uuid.UUID
    ) -> list[dict[str, str | int]]:
        stmt = (
            select(
                RiskEntry.likelihood,
                RiskEntry.severity,
                func.count().label("count"),
            )
            .where(RiskEntry.organization_id == organization_id)
            .group_by(RiskEntry.likelihood, RiskEntry.severity)
        )
        result = await self._db.execute(stmt)
        return [
            {"likelihood": row.likelihood, "severity": row.severity, "count": row.count}
            for row in result.all()
        ]

    async def get_recent_activity(
        self, organization_id: uuid.UUID, limit: int = 20
    ) -> list[AuditEntry]:
        stmt = (
            select(AuditEntry)
            .where(AuditEntry.organization_id == organization_id)
            .order_by(AuditEntry.timestamp.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
