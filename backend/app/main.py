from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from app.services.microsoft_graph import MicrosoftGraphService
    from app.services.openai_client import AzureOpenAIClient
    from app.services.rag import RAGService
    from app.services.risk_outcome_importer import RiskOutcomeImporter
    from app.services.search_indexer import SearchIndexer
    from app.services.sharepoint_crawler import SharePointCrawler
    from app.services.storage import BlobStorageService

logger = structlog.get_logger(__name__)

ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["Authorization", "Content-Type", "X-Organization-ID", "X-Correlation-ID"]


class ServiceRegistry:
    """Centralized lifecycle manager for Azure service clients."""

    def __init__(self) -> None:
        self._openai_client: AzureOpenAIClient | None = None
        self._rag_service: RAGService | None = None
        self._storage_service: BlobStorageService | None = None
        self._search_indexer: SearchIndexer | None = None
        self._graph_service: MicrosoftGraphService | None = None
        self._sharepoint_crawler: SharePointCrawler | None = None
        self._risk_outcome_importer: RiskOutcomeImporter | None = None

    async def startup(self) -> None:
        from app.services.microsoft_graph import MicrosoftGraphService
        from app.services.openai_client import AzureOpenAIClient
        from app.services.rag import RAGService
        from app.services.risk_outcome_importer import RiskOutcomeImporter
        from app.services.search_indexer import SearchIndexer
        from app.services.sharepoint_crawler import SharePointCrawler
        from app.services.storage import BlobStorageService

        self._openai_client = AzureOpenAIClient()
        self._rag_service = RAGService(self._openai_client)
        self._storage_service = BlobStorageService()
        self._search_indexer = SearchIndexer()
        self._graph_service = MicrosoftGraphService()
        self._sharepoint_crawler = SharePointCrawler()
        self._risk_outcome_importer = RiskOutcomeImporter(self._sharepoint_crawler)
        logger.info("service_registry_initialized")

    async def shutdown(self) -> None:
        if self._sharepoint_crawler:
            await self._sharepoint_crawler.close()
        if self._graph_service:
            await self._graph_service.close()
        if self._search_indexer:
            await self._search_indexer.close()
        if self._rag_service:
            await self._rag_service.close()
        if self._openai_client:
            await self._openai_client.close()
        if self._storage_service:
            await self._storage_service.close()
        logger.info("service_registry_shutdown")

    @property
    def openai_client(self) -> AzureOpenAIClient:
        if self._openai_client is None:
            raise RuntimeError("ServiceRegistry not initialized — call startup() first")
        return self._openai_client

    @property
    def rag_service(self) -> RAGService:
        if self._rag_service is None:
            raise RuntimeError("ServiceRegistry not initialized — call startup() first")
        return self._rag_service

    @property
    def storage_service(self) -> BlobStorageService:
        if self._storage_service is None:
            raise RuntimeError("ServiceRegistry not initialized — call startup() first")
        return self._storage_service

    @property
    def search_indexer(self) -> SearchIndexer:
        if self._search_indexer is None:
            raise RuntimeError("ServiceRegistry not initialized — call startup() first")
        return self._search_indexer

    @property
    def graph_service(self) -> MicrosoftGraphService:
        if self._graph_service is None:
            raise RuntimeError("ServiceRegistry not initialized — call startup() first")
        return self._graph_service

    @property
    def sharepoint_crawler(self) -> SharePointCrawler:
        if self._sharepoint_crawler is None:
            raise RuntimeError("ServiceRegistry not initialized — call startup() first")
        return self._sharepoint_crawler

    @property
    def risk_outcome_importer(self) -> RiskOutcomeImporter:
        if self._risk_outcome_importer is None:
            raise RuntimeError("ServiceRegistry not initialized — call startup() first")
        return self._risk_outcome_importer


service_registry = ServiceRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()

    if settings.app_env != "development":
        origins = settings.cors_origins_list
        if "*" in origins:
            raise RuntimeError(
                "CORS_ORIGINS must not contain '*' outside of local development. "
                "Set explicit origins in CORS_ORIGINS environment variable."
            )

    await service_registry.startup()
    app.state.services = service_registry

    import asyncio as _asyncio

    from app.core.tasks import drain_all_tasks, track_task
    from app.services.digest_worker import run_digest_worker
    from app.services.email import get_email_service

    digest_stop = _asyncio.Event()
    digest_task = _asyncio.create_task(run_digest_worker(digest_stop))
    track_task(digest_task, name="notification.digest_worker")

    yield

    digest_stop.set()
    await drain_all_tasks()
    await get_email_service().close()
    await service_registry.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
    )

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(api_router)

    from app.core.telemetry import configure_telemetry

    configure_telemetry(app)

    return app


app = create_app()
