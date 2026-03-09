"""Dependency injection functions for FastAPI endpoints."""

from app.core.deps.auth import (
    LAST_LOGIN_THROTTLE,
    get_current_user,
    get_token_payload,
)
from app.core.deps.common import get_audit_logger, get_correlation_id
from app.core.deps.organization import (
    get_current_organization,
    require_org_role,
    require_platform_admin,
)
from app.core.deps.services import (
    get_graph_service,
    get_openai_client,
    get_rag_service,
    get_search_indexer,
    get_storage_service,
)

__all__ = [
    "LAST_LOGIN_THROTTLE",
    "get_audit_logger",
    "get_correlation_id",
    "get_current_organization",
    "get_current_user",
    "get_graph_service",
    "get_openai_client",
    "get_rag_service",
    "get_search_indexer",
    "get_storage_service",
    "get_token_payload",
    "require_org_role",
    "require_platform_admin",
]
