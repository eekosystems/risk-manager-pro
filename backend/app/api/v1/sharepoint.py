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
)
from app.core.tasks import track_task
from app.models.document import SourceType
from app.repositories.document import DocumentRepository
from app.schemas.common import DataResponse, MetaResponse
from app.services.document_processor import DocumentProcessor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.main import ServiceRegistry
    from app.models.organization import Organization
    from app.models.user import User
    from app.services.audit import AuditLogger
    from app.services.sharepoint_crawler import SharePointCrawler, SharePointFile

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
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[CrawlResult]:
    """Discover files on SharePoint and queue them for background download + processing."""
    crawler: SharePointCrawler = request.app.state.services.sharepoint_crawler
    registry = request.app.state.services

    files: list[SharePointFile] = await crawler.discover_files(drive_name=drive_name)

    repo = DocumentRepository(db)
    existing_docs, _ = await repo.list_for_organization(organization.id, skip=0, limit=10000)
    existing_keys = {(doc.filename, doc.folder_path or "") for doc in existing_docs}

    to_import: list[SharePointFile] = []
    skipped: list[str] = []

    for file in files:
        if (file.name, file.folder_path or "") in existing_keys:
            skipped.append(file.name)
        else:
            to_import.append(file)

    if to_import:
        task = asyncio.create_task(
            _crawl_background(
                files=to_import,
                organization_id=organization.id,
                user_id=current_user.id,
                source_type=source_type,
                registry=registry,
            )
        )
        track_task(task)

    await audit.log(
        action="sharepoint.crawl",
        user=current_user,
        resource_type="sharepoint",
        resource_id=str(organization.id),
        organization_id=organization.id,
    )

    result = CrawlResult(
        files_discovered=len(files),
        files_queued=len(to_import),
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
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[SyncFolderResult]:
    """Discover files in a folder and queue background re-download + reprocess."""
    crawler: SharePointCrawler = request.app.state.services.sharepoint_crawler
    registry = request.app.state.services

    sp_files: list[SharePointFile] = await crawler.discover_folder(folder_path)

    repo = DocumentRepository(db)
    existing_docs, _ = await repo.list_for_organization(organization.id, skip=0, limit=10000)
    existing_by_key = {(doc.filename, doc.folder_path or ""): doc for doc in existing_docs}

    to_update: list[tuple[SharePointFile, uuid.UUID, str]] = []
    to_create: list[SharePointFile] = []

    for file in sp_files:
        existing = existing_by_key.get((file.name, file.folder_path or ""))
        if existing:
            to_update.append((file, existing.id, existing.blob_path))
        else:
            to_create.append(file)

    if to_update or to_create:
        task = asyncio.create_task(
            _sync_folder_background(
                to_update=to_update,
                to_create=to_create,
                organization_id=organization.id,
                user_id=current_user.id,
                source_type=source_type,
                registry=registry,
            )
        )
        track_task(task)

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
        files_updated=len(to_update),
        files_new=len(to_create),
    )
    return DataResponse(data=result, meta=MetaResponse(request_id=""))


async def _crawl_background(
    files: list[SharePointFile],
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    source_type: SourceType,
    registry: ServiceRegistry,
) -> None:
    """Phase 1: download all files. Phase 2: process them."""
    crawler = registry.sharepoint_crawler
    doc_ids: list[uuid.UUID] = []

    # Phase 1 — download and create DB records (fast, files appear in UI immediately)
    for file in files:
        try:
            data = await crawler.download_file(file)
            async with async_session_factory() as db:
                repo = DocumentRepository(db)
                blob_path = f"{organization_id}/{uuid.uuid4()}/{file.name}"
                await registry.storage_service.upload(blob_path, data, file.content_type)
                document = await repo.create(
                    organization_id=organization_id,
                    uploaded_by=user_id,
                    filename=file.name,
                    blob_path=blob_path,
                    content_type=file.content_type,
                    size_bytes=len(data),
                    source_type=source_type,
                    folder_path=file.folder_path,
                )
                await db.commit()
                doc_ids.append(document.id)
        except Exception:
            logger.error("crawl_file_failed", filename=file.name, exc_info=True)

    logger.info("crawl_download_phase_complete", downloaded=len(doc_ids), total=len(files))

    # Phase 2 — process each document (slow, but files are already visible)
    for doc_id in doc_ids:
        await _process_doc(doc_id, registry)


async def _sync_folder_background(
    to_update: list[tuple[SharePointFile, uuid.UUID, str]],
    to_create: list[SharePointFile],
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    source_type: SourceType,
    registry: ServiceRegistry,
) -> None:
    """Phase 1: re-download all files. Phase 2: reprocess them."""
    from app.models.document import DocumentStatus

    crawler = registry.sharepoint_crawler
    doc_ids: list[uuid.UUID] = []

    # Phase 1a — re-download existing files
    for file, doc_id, blob_path in to_update:
        try:
            data = await crawler.download_file(file)
            await registry.search_indexer.delete_by_document(doc_id)
            await registry.storage_service.upload(blob_path, data, file.content_type)
            async with async_session_factory() as db:
                repo = DocumentRepository(db)
                await repo.update_status(doc_id, DocumentStatus.UPLOADED)
                await db.commit()
            doc_ids.append(doc_id)
        except Exception:
            logger.error("sync_update_failed", filename=file.name, exc_info=True)

    # Phase 1b — download new files
    for file in to_create:
        try:
            data = await crawler.download_file(file)
            async with async_session_factory() as db:
                repo = DocumentRepository(db)
                blob_path = f"{organization_id}/{uuid.uuid4()}/{file.name}"
                await registry.storage_service.upload(blob_path, data, file.content_type)
                document = await repo.create(
                    organization_id=organization_id,
                    uploaded_by=user_id,
                    filename=file.name,
                    blob_path=blob_path,
                    content_type=file.content_type,
                    size_bytes=len(data),
                    source_type=source_type,
                    folder_path=file.folder_path,
                )
                await db.commit()
                doc_ids.append(document.id)
        except Exception:
            logger.error("sync_create_failed", filename=file.name, exc_info=True)

    logger.info(
        "sync_download_phase_complete",
        downloaded=len(doc_ids),
        total=len(to_update) + len(to_create),
    )

    # Phase 2 — process all documents
    for doc_id in doc_ids:
        await _process_doc(doc_id, registry)


async def _process_doc(document_id: uuid.UUID, registry: ServiceRegistry) -> None:
    """Run the document processing pipeline."""
    async with async_session_factory() as db:
        try:
            repo = DocumentRepository(db)
            processor = DocumentProcessor(
                storage=registry.storage_service,
                openai_client=registry.openai_client,
                indexer=registry.search_indexer,
                repo=repo,
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
