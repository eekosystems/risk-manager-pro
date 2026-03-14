import asyncio
import json
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import Request  # noqa: TCH002
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import async_session_factory
from app.core.tasks import track_task
from app.models.audit import AuditEntry
from app.models.user import User  # noqa: TCH001
from app.services.storage import BlobStorageService  # noqa: TCH001

logger = structlog.get_logger(__name__)


class AuditLogger:
    def __init__(
        self,
        request: Request,
        storage: BlobStorageService | None = None,
    ) -> None:
        self._request = request
        self._storage = storage

    async def log(
        self,
        action: str,
        user: User,
        resource_type: str = "",
        resource_id: str | None = None,
        outcome: str = "success",
        metadata: dict[str, object] | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> None:
        correlation_id = getattr(self._request.state, "correlation_id", str(uuid.uuid4()))
        ip_address = self._request.client.host if self._request.client else "unknown"
        user_agent = self._request.headers.get("User-Agent", "unknown")[:500]

        task = asyncio.create_task(
            _write_audit_entry(
                user_id=user.id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=uuid.UUID(correlation_id),
                outcome=outcome,
                metadata_json=metadata,
                organization_id=organization_id,
                storage=self._storage,
            )
        )
        track_task(task)


async def _write_audit_entry(
    user_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: str | None,
    ip_address: str,
    user_agent: str,
    correlation_id: uuid.UUID,
    outcome: str,
    metadata_json: dict[str, object] | None,
    organization_id: uuid.UUID | None,
    storage: BlobStorageService | None = None,
) -> None:
    try:
        async with async_session_factory() as session:
            entry = AuditEntry(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
                outcome=outcome,
                metadata_json=metadata_json,
                organization_id=organization_id,
            )
            session.add(entry)
            await session.commit()

        logger.info(
            "audit_entry_created",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            user_id=str(user_id),
        )

        # Write WORM audit blob backup
        await _write_audit_blob(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            outcome=outcome,
            metadata_json=metadata_json,
            organization_id=organization_id,
            storage=storage,
        )

    except SQLAlchemyError:
        logger.error(
            "audit_entry_failed",
            action=action,
            resource_type=resource_type,
            user_id=str(user_id),
            alert_category="soc2_audit_failure",
            exc_info=True,
        )


async def _write_audit_blob(
    user_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: str | None,
    ip_address: str,
    user_agent: str,
    correlation_id: uuid.UUID,
    outcome: str,
    metadata_json: dict[str, object] | None,
    organization_id: uuid.UUID | None,
    storage: BlobStorageService | None = None,
) -> None:
    try:
        from app.core.config import settings

        if not settings.azure_storage_account_name and not settings.azure_storage_connection_string:
            return

        from app.services.storage import BlobStorageService

        now = datetime.now(UTC)
        blob_path = f"audit/{now.year}/{now.month:02d}/{now.day:02d}/{correlation_id}.json"

        audit_data = {
            "timestamp": now.isoformat(),
            "user_id": str(user_id),
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "correlation_id": str(correlation_id),
            "outcome": outcome,
            "metadata": metadata_json,
            "organization_id": str(organization_id) if organization_id else None,
        }

        owns_storage = False
        if storage is None:
            storage = BlobStorageService()
            owns_storage = True
        try:
            await storage.upload(
                blob_path=blob_path,
                data=json.dumps(audit_data).encode("utf-8"),
                content_type="application/json",
                container=settings.azure_storage_audit_container,
            )
        finally:
            if owns_storage:
                await storage.close()

    except (OSError, ValueError):
        logger.error(
            "audit_blob_write_failed",
            correlation_id=str(correlation_id),
            alert_category="soc2_audit_failure",
            exc_info=True,
        )
