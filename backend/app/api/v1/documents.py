import asyncio
import uuid

import structlog
from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    get_current_user,
    get_storage_service,
)
from app.core.tasks import track_task
from app.models.organization import Organization
from app.models.user import User
from app.repositories.document import DocumentRepository
from app.schemas.common import DataResponse, MetaResponse, PaginatedMeta, PaginatedResponse
from app.schemas.document import DocumentDetail, DocumentListItem, DocumentResponse
from app.services.audit import AuditLogger
from app.services.document import DocumentService
from app.services.document_processor import DocumentProcessor
from app.services.openai_client import AzureOpenAIClient
from app.services.search_indexer import SearchIndexer
from app.services.storage import BlobStorageService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_document_service(
    db: AsyncSession = Depends(get_db),
    storage: BlobStorageService = Depends(get_storage_service),
) -> DocumentService:
    return DocumentService(db=db, storage=storage)


@router.post("/upload", response_model=DataResponse[DocumentResponse], status_code=201)
async def upload_document(
    file: UploadFile,
    request: Request,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: DocumentService = Depends(_get_document_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[DocumentResponse]:
    data = await file.read()
    document = await service.upload(
        user=current_user,
        organization_id=organization.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    await audit.log(
        action="document.uploaded",
        user=current_user,
        resource_type="document",
        resource_id=str(document.id),
        organization_id=organization.id,
    )

    registry = request.app.state.services
    task = asyncio.create_task(
        _process_document_background(
            document_id=document.id,
            storage=registry.storage_service,
            openai_client=registry.openai_client,
            search_indexer=registry.search_indexer,
        )
    )
    track_task(task)

    return DataResponse(
        data=DocumentResponse.model_validate(document),
        meta=MetaResponse(request_id=str(document.id)),
    )


async def _process_document_background(
    document_id: uuid.UUID,
    storage: BlobStorageService,
    openai_client: AzureOpenAIClient,
    search_indexer: SearchIndexer,
) -> None:
    """Run document processing in a background task with its own DB session."""
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
                "background_processing_failed",
                document_id=str(document_id),
                exc_info=True,
            )


@router.get("", response_model=PaginatedResponse[DocumentListItem])
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: DocumentService = Depends(_get_document_service),
) -> PaginatedResponse[DocumentListItem]:
    documents, total = await service.list_documents(
        organization_id=organization.id, skip=skip, limit=limit
    )
    items = [DocumentListItem.model_validate(d) for d in documents]
    total_pages = (total + limit - 1) // limit
    return PaginatedResponse(
        data=items,
        meta=PaginatedMeta(
            request_id="",
            total=total,
            page=(skip // limit) + 1,
            page_size=limit,
            total_pages=total_pages,
        ),
    )


@router.get("/{document_id}", response_model=DataResponse[DocumentDetail])
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: DocumentService = Depends(_get_document_service),
) -> DataResponse[DocumentDetail]:
    document = await service.get_document(document_id, organization.id)
    return DataResponse(
        data=DocumentDetail.model_validate(document),
        meta=MetaResponse(request_id=str(document_id)),
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    service: DocumentService = Depends(_get_document_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    await service.delete_document(document_id, organization.id)
    await audit.log(
        action="document.deleted",
        user=current_user,
        resource_type="document",
        resource_id=str(document_id),
        organization_id=organization.id,
    )
