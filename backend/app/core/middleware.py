import json
import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger(__name__)


class CorrelationIdMiddleware:
    """Pure ASGI middleware for correlation ID and structured logging context.

    Uses raw ASGI protocol instead of BaseHTTPMiddleware to avoid the known
    Starlette bug where BaseHTTPMiddleware can produce responses that bypass
    CORSMiddleware's header injection during error scenarios.

    Also catches unhandled exceptions to ensure a proper HTTP 500 response is
    returned *within* the middleware chain, so the outer CORSMiddleware always
    has the chance to inject CORS headers.
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

        # Track whether response headers have already been sent
        response_started = False

        async def send_with_correlation_id(message: Any) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_id)
        except Exception:
            logger.error(
                "unhandled_exception_in_middleware",
                correlation_id=correlation_id,
                path=scope.get("path", ""),
                method=scope.get("method", ""),
                exc_info=True,
            )
            # Only send an error response if headers haven't been sent yet
            if not response_started:
                body = json.dumps(
                    {"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}}
                ).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("latin-1")),
                            (b"x-correlation-id", correlation_id.encode("latin-1")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
