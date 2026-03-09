import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource} with id '{resource_id}' not found",
            status_code=404,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(code="FORBIDDEN", message=message, status_code=403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(code="UNAUTHORIZED", message=message, status_code=401)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(code="CONFLICT", message=message, status_code=409)


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=422)


class TooManyRequestsError(AppError):
    def __init__(self, message: str = "Too many requests") -> None:
        super().__init__(code="TOO_MANY_REQUESTS", message=message, status_code=429)


class ExternalServiceError(AppError):
    def __init__(self, service: str, message: str) -> None:
        super().__init__(
            code="EXTERNAL_SERVICE_ERROR",
            message=f"{service}: {message}",
            status_code=502,
        )


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    logger.error(
        "unhandled_error",
        error_type=type(exc).__name__,
        error=str(exc),
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}},
    )
