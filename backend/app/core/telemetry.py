"""Azure Monitor / OpenTelemetry wiring.

Invoked from app.main.create_app when APPLICATIONINSIGHTS_CONNECTION_STRING
is set. Unset → no-op so local dev and tests are unaffected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger(__name__)

_configured = False


def configure_telemetry(app: FastAPI) -> None:
    global _configured
    if _configured:
        return
    if not settings.applicationinsights_connection_string:
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        logger.warning(
            "telemetry_dependencies_missing", extra={"sdk": "azure-monitor-opentelemetry"}
        )
        return

    configure_azure_monitor(
        connection_string=settings.applicationinsights_connection_string,
        logger_name="app",
        instrumentation_options={
            "azure_sdk": {"enabled": True},
            "django": {"enabled": False},
            "fastapi": {"enabled": False},
            "flask": {"enabled": False},
            "psycopg2": {"enabled": False},
            "requests": {"enabled": True},
            "urllib": {"enabled": True},
            "urllib3": {"enabled": True},
        },
    )

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()

    _configured = True
    logger.info(
        "telemetry_configured",
        service_name=settings.otel_service_name,
        sampler_arg=settings.otel_traces_sampler_arg,
    )
