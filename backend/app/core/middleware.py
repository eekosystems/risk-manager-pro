import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send


class CorrelationIdMiddleware:
    """Pure ASGI middleware for correlation ID and structured logging context.

    Uses raw ASGI protocol instead of BaseHTTPMiddleware to avoid the known
    Starlette bug where BaseHTTPMiddleware can produce responses that bypass
    CORSMiddleware's header injection during error scenarios.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract correlation ID from request headers
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode("latin-1") or str(
            uuid.uuid4()
        )
        organization_id = headers.get(b"x-organization-id", b"").decode("latin-1")

        # Bind structured logging context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            organization_id=organization_id,
        )

        # Store correlation_id in scope state for downstream access
        scope.setdefault("state", {})
        scope["state"]["correlation_id"] = correlation_id

        async def send_with_correlation_id(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_correlation_id)
