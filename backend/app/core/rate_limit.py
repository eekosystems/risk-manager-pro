"""API rate limiting using slowapi.

Three tiers:
- Health endpoints: exempt
- General API: 60/minute (configurable)
- AI/chat endpoints: 20/minute (configurable)

Set RATE_LIMIT_STORAGE_URI to a Redis URL (e.g. redis://host:6379) for
multi-instance deployments. Falls back to in-memory when unset.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

_storage_uri = settings.rate_limit_storage_uri or None

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    storage_uri=_storage_uri,
)


async def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded: {exc.detail}",
            }
        },
    )
