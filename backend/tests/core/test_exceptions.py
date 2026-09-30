"""Tests for the application error handler."""

import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import AppError, ForbiddenError, app_error_handler


def _app_with_refusing_route() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.get("/refused")
    async def refused() -> None:
        raise ForbiddenError("Requires one of roles: org_admin")

    return app


async def test_app_error_returns_error_envelope() -> None:
    transport = ASGITransport(app=_app_with_refusing_route())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/refused")

    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "FORBIDDEN", "message": "Requires one of roles: org_admin"}
    }


async def test_app_error_is_logged_with_code_and_path_but_not_message() -> None:
    transport = ASGITransport(app=_app_with_refusing_route())
    with structlog.testing.capture_logs() as logs:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/refused")

    refused = [entry for entry in logs if entry["event"] == "request_refused"]
    assert len(refused) == 1
    entry = refused[0]
    assert entry["log_level"] == "warning"
    assert entry["code"] == "FORBIDDEN"
    assert entry["status_code"] == 403
    assert entry["method"] == "GET"
    assert entry["path"] == "/refused"
    assert "correlation_id" in entry
    assert "Requires one of roles" not in str(entry)
