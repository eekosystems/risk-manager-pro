from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from app.services.audit import AuditLogger


async def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


async def get_audit_logger(request: Request) -> AuditLogger:
    from app.services.audit import AuditLogger

    registry = getattr(request.app.state, "services", None)
    storage = registry.storage_service if registry else None
    return AuditLogger(request=request, storage=storage)
