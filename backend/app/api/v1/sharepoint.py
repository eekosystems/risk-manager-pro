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
    get_search_indexer,
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


class SyncFolderResult(BaseModel):
    folder_path: str
    files_found: int
    files_updated: int
    files_new: int


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
    existing_keys = {(doc.filename, doc.folder_path or "") for doc in existing_docs}

    queued_count = 0
    skipped: list[str] = []

    for file in files:
        file_key = (file.name, file.folder_path or "")
        if file_key in existing_keys:
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
            folder_path=file.folder_path,
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


@router.post("/sync-folder", response_model=DataResponse[SyncFolderResult])
async def sync_folder(
    request: Request,
    folder_path: str = Query(..., description="Folder path to re-sync from SharePoint"),
    source_type: SourceType = Query(SourceType.CLIENT, alias="source_type"),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    storage: BlobStorageService = Depends(get_storage_service),
    indexer: SearchIndexer = Depends(get_search_indexer),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[SyncFolderResult]:
    """Re-download files in a folder from SharePoint and reprocess them."""
    from app.models.document import DocumentStatus

    crawler: SharePointCrawler = request.app.state.services.sharepoint_crawler
    registry = request.app.state.services

    sp_files: list[SharePointFile] = await crawler.discover_folder(folder_path)

    repo = DocumentRepository(db)
    existing_docs, _ = await repo.list_for_organization(organization.id, skip=0, limit=10000)
    existing_by_key = {(doc.filename, doc.folder_path or ""): doc for doc in existing_docs}

    updated = 0
    new_count = 0

    for file in sp_files:
        file_key = (file.name, file.folder_path or "")
        data = await crawler.download_file(file)
        existing = existing_by_key.get(file_key)

        if existing:
            await indexer.delete_by_document(existing.id)
            await storage.upload(existing.blob_path, data, file.content_type)
            await repo.update_status(
                existing.id, DocumentStatus.UPLOADED, organization_id=organization.id
            )
            await db.commit()
            task = asyncio.create_task(
                _process_sharepoint_doc(
                    document_id=existing.id,
                    storage=registry.storage_service,
                    openai_client=registry.openai_client,
                    search_indexer=registry.search_indexer,
                )
            )
            track_task(task)
            updated += 1
        else:
            blob_path = f"{organization.id}/{uuid.uuid4()}/{file.name}"
            await storage.upload(blob_path, data, file.content_type)
            document = await repo.create(
                organization_id=organization.id,
                uploaded_by=current_user.id,
                filename=file.name,
                blob_path=blob_path,
                content_type=file.content_type,
                size_bytes=len(data),
                source_type=source_type,
                folder_path=file.folder_path,
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
            new_count += 1

    await audit.log(
        action="sharepoint.sync_folder",
        user=current_user,
        resource_type="sharepoint",
        resource_id=folder_path,
        organization_id=organization.id,
    )

    result = SyncFolderResult(
        folder_path=folder_path,
        files_found=len(sp_files),
        files_updated=updated,
        files_new=new_count,
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
