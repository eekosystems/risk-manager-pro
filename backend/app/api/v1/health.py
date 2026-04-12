from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.tasks import get_task_failure_counts

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]
    checked_at: str
    background_task_failures: dict[str, int]


@router.get("/health", response_model=HealthResponse)
@limiter.exempt  # type: ignore[untyped-decorator]
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version=settings.app_version)


@router.get("/health/ready", response_model=ReadyResponse)
@limiter.exempt  # type: ignore[untyped-decorator]
async def readiness_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ReadyResponse:
    checks: dict[str, str] = {}

    # Database connectivity
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # Deliberately broad: any failure means service is unhealthy
        logger.warning("health_check_database_failed", error=str(e))
        checks["database"] = "unavailable"

    # Azure AI Search connectivity
    checks["search"] = await _check_search()

    # Azure OpenAI connectivity
    checks["openai"] = await _check_openai()

    # Azure Blob Storage connectivity
    checks["storage"] = await _check_storage(request)

    db_ok = checks["database"] == "ok"
    all_ok = all(v == "ok" for v in checks.values())

    if all_ok:
        status = "healthy"
    elif db_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return ReadyResponse(
        status=status,
        checks=checks,
        checked_at=datetime.now(UTC).isoformat(),
        background_task_failures=get_task_failure_counts(),
    )


async def _check_search() -> str:
    if not settings.azure_search_endpoint:
        return "not_configured"
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.search.documents.aio import SearchClient

        credential = DefaultAzureCredential()
        client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        )
        try:
            await client.get_document_count()
            return "ok"
        finally:
            await client.close()
            await credential.close()
    except Exception as e:  # Deliberately broad: any failure means service is unhealthy
        logger.warning("health_check_search_failed", error=str(e))
        return "unavailable"


async def _check_openai() -> str:
    if not settings.azure_openai_endpoint:
        return "not_configured"
    try:
        from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
        from openai import AsyncAzureOpenAI

        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            azure_ad_token_provider=token_provider,
        )
        try:
            await client.models.list()
            return "ok"
        finally:
            await credential.close()
    except Exception as e:  # Deliberately broad: any failure means service is unhealthy
        logger.warning("health_check_openai_failed", error=str(e))
        return "unavailable"


async def _check_storage(request: Request) -> str:
    if not settings.azure_storage_account_name and not settings.azure_storage_connection_string:
        return "not_configured"
    try:
        storage = request.app.state.services.storage_service
        client = await storage._get_client()
        container = client.get_container_client(settings.azure_storage_container_name)
        await container.get_container_properties()
        return "ok"
    except Exception as e:  # Deliberately broad: any failure means service is unhealthy
        logger.warning("health_check_storage_failed", error=str(e))
        return "unavailable"
