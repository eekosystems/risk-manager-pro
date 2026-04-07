"""SharePoint document crawling endpoints."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.core.database import async_session_factory, get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    get_current_user,
    get_storage_service,
)
from app.core.tasks import track_task
from app.models.document import SourceType
from app.repositories.document import DocumentRepository
from app.schemas.common import DataResponse, MetaResponse
from app.services.document_processor import DocumentProcessor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.organization import Organization
    from app.models.user import User
    from app.services.audit import AuditLogger
    from app.services.openai_client import AzureOpenAIClient
    from app.services.search_indexer import SearchIndexer
    from app.services.sharepoint_crawler import SharePointCrawler, SharePointFile
    from app.services.storage import BlobStorageService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sharepoint", tags=["sharepoint"])


class CrawlResult(BaseModel):
    files_discovered: int
    files_queued: int
    skipped_files: list[str]


class DriveInfo(BaseModel):
    id: str
    name: str
    web_url: str


class DrivesResponse(BaseModel):
    drives: list[DriveInfo]


@router.get("/drives", response_model=DataResponse[DrivesResponse])
async def list_drives(
    request: Request,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
) -> DataResponse[DrivesResponse]:
    """List available document libraries in the configured SharePoint site."""
    crawler: SharePointCrawler = request.app.state.services.sharepoint_crawler
    raw_drives = await crawler.list_drives()
    drives = [
        DriveInfo(
            id=d["id"],
            name=d.get("name", "Unnamed"),
            web_url=d.get("webUrl", ""),
        )
        for d in raw_drives
    ]
    return DataResponse(
        data=DrivesResponse(drives=drives),
        meta=MetaResponse(request_id=""),
    )


@router.post("/crawl", response_model=DataResponse[CrawlResult])
async def crawl_sharepoint(
    request: Request,
    drive_name: str | None = Query(None, description="Specific drive/library name to crawl"),
    source_type: SourceType = Query(SourceType.CLIENT, alias="source_type"),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    storage: BlobStorageService = Depends(get_storage_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[CrawlResult]:
    """Crawl SharePoint and queue discovered documents for processing."""
    crawler: SharePointCrawler = request.app.state.services.sharepoint_crawler
    registry = request.app.state.services

    files: list[SharePointFile] = await crawler.discover_files(drive_name=drive_name)

    repo = DocumentRepository(db)
    existing_docs, _ = await repo.list_for_organization(organization.id, skip=0, limit=10000)
    existing_filenames = {doc.filename for doc in existing_docs}

    queued_count = 0
    skipped: list[str] = []

    for file in files:
        if file.name in existing_filenames:
            skipped.append(file.name)
            continue

        blob_path = f"{organization.id}/{uuid.uuid4()}/{file.name}"
        data = await crawler.download_file(file)

        await storage.upload(blob_path, data, file.content_type)

        document = await repo.create(
            organization_id=organization.id,
            uploaded_by=current_user.id,
            filename=file.name,
            blob_path=blob_path,
            content_type=file.content_type,
            size_bytes=len(data),
            source_type=source_type,
        )
        await db.commit()

        task = asyncio.create_task(
            _process_sharepoint_doc(
                document_id=document.id,
                storage=registry.storage_service,
                openai_client=registry.openai_client,
                search_indexer=registry.search_indexer,
            )
        )
        track_task(task)
        queued_count += 1

    await audit.log(
        action="sharepoint.crawl",
        user=current_user,
        resource_type="sharepoint",
        resource_id=str(organization.id),
        organization_id=organization.id,
    )

    result = CrawlResult(
        files_discovered=len(files),
        files_queued=queued_count,
        skipped_files=skipped,
    )
    return DataResponse(data=result, meta=MetaResponse(request_id=""))


async def _process_sharepoint_doc(
    document_id: uuid.UUID,
    storage: BlobStorageService,
    openai_client: AzureOpenAIClient,
    search_indexer: SearchIndexer,
) -> None:
    """Process a SharePoint document in a background task."""
    async with async_session_factory() as db:
        try:
            repo = DocumentRepository(db)
            processor = DocumentProcessor(
                storage=storage, openai_client=openai_client, indexer=search_indexer, repo=repo
            )
            await processor.process(document_id)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error(
                "sharepoint_doc_processing_failed",
                document_id=str(document_id),
                exc_info=True,
            )
