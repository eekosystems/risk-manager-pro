import csv
import io
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditRepository
from app.schemas.audit import AuditEntryResponse


class AuditQueryService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = AuditRepository(db)

    async def list_entries(
        self,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditEntryResponse], int]:
        entries, total = await self._repo.list_entries(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )
        return [AuditEntryResponse.model_validate(e) for e in entries], total

    async def export_csv(
        self,
        organization_id: uuid.UUID,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> str:
        entries, _ = await self._repo.list_entries(
            organization_id=organization_id,
            skip=0,
            limit=10000,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "outcome",
            "ip_address",
            "correlation_id",
        ])
        for entry in entries:
            writer.writerow([
                entry.timestamp.isoformat(),
                str(entry.user_id),
                entry.action,
                entry.resource_type,
                entry.resource_id or "",
                entry.outcome,
                entry.ip_address,
                str(entry.correlation_id),
            ])
        return output.getvalue()

    async def get_filter_options(
        self, organization_id: uuid.UUID
    ) -> dict[str, list[str]]:
        actions = await self._repo.get_distinct_actions(organization_id)
        resource_types = await self._repo.get_distinct_resource_types(organization_id)
        return {
            "actions": actions,
            "resource_types": resource_types,
            "outcomes": ["success", "failure", "denied"],
        }
