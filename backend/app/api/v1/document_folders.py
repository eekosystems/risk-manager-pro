import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_correlation_id,
    get_current_organization,
    require_analyst_or_above,
    require_any_member,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import DataResponse, MetaResponse
from app.schemas.document_folder import (
    CreateFolderRequest,
    DocumentFolderResponse,
    MoveFolderRequest,
    RenameFolderRequest,
)
from app.services.audit import AuditLogger
from app.services.document_folder import DocumentFolderService

router = APIRouter(prefix="/document-folders", tags=["document-folders"])


def _get_folder_service(db: AsyncSession = Depends(get_db)) -> DocumentFolderService:
    return DocumentFolderService(db=db)


@router.get("", response_model=DataResponse[list[DocumentFolderResponse]])
async def list_folders(
    _current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: DocumentFolderService = Depends(_get_folder_service),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[list[DocumentFolderResponse]]:
    folders = await service.list_folders(organization.id)
    return DataResponse(
        data=[DocumentFolderResponse.model_validate(f) for f in folders],
        meta=MetaResponse(request_id=correlation_id),
    )


@router.post("", response_model=DataResponse[DocumentFolderResponse], status_code=201)
async def create_folder(
    payload: CreateFolderRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: DocumentFolderService = Depends(_get_folder_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[DocumentFolderResponse]:
    folder = await service.create_folder(
        organization_id=organization.id,
        created_by=current_user.id,
        name=payload.name,
        parent_id=payload.parent_id,
    )
    await audit.log(
        action="document_folder.created",
        user=current_user,
        resource_type="document_folder",
        resource_id=str(folder.id),
        organization_id=organization.id,
        metadata={"name": folder.name, "parent_id": str(folder.parent_id or "")},
    )
    return DataResponse(
        data=DocumentFolderResponse.model_validate(folder),
        meta=MetaResponse(request_id=correlation_id),
    )


@router.patch("/{folder_id}", response_model=DataResponse[DocumentFolderResponse])
async def rename_folder(
    folder_id: uuid.UUID,
    payload: RenameFolderRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: DocumentFolderService = Depends(_get_folder_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[DocumentFolderResponse]:
    folder = await service.rename_folder(folder_id, organization.id, payload.name)
    await audit.log(
        action="document_folder.renamed",
        user=current_user,
        resource_type="document_folder",
        resource_id=str(folder_id),
        organization_id=organization.id,
        metadata={"name": folder.name},
    )
    return DataResponse(
        data=DocumentFolderResponse.model_validate(folder),
        meta=MetaResponse(request_id=correlation_id),
    )


@router.patch("/{folder_id}/parent", response_model=DataResponse[DocumentFolderResponse])
async def move_folder(
    folder_id: uuid.UUID,
    payload: MoveFolderRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: DocumentFolderService = Depends(_get_folder_service),
    audit: AuditLogger = Depends(get_audit_logger),
    correlation_id: str = Depends(get_correlation_id),
) -> DataResponse[DocumentFolderResponse]:
    folder = await service.move_folder(folder_id, organization.id, payload.parent_id)
    await audit.log(
        action="document_folder.moved",
        user=current_user,
        resource_type="document_folder",
        resource_id=str(folder_id),
        organization_id=organization.id,
        metadata={"parent_id": str(payload.parent_id or "")},
    )
    return DataResponse(
        data=DocumentFolderResponse.model_validate(folder),
        meta=MetaResponse(request_id=correlation_id),
    )


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: DocumentFolderService = Depends(_get_folder_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    await service.delete_folder(folder_id, organization.id)
    await audit.log(
        action="document_folder.deleted",
        user=current_user,
        resource_type="document_folder",
        resource_id=str(folder_id),
        organization_id=organization.id,
    )
