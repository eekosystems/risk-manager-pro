"""Tests for the in-app document folder service."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.repositories.document import DocumentRepository
from app.services.document_folder import MAX_FOLDER_DEPTH, DocumentFolderService
from tests.conftest import make_test_organization, make_test_user


async def _seed(db: AsyncSession) -> tuple[User, uuid.UUID]:
    org = make_test_organization()
    db.add(org)
    await db.flush()

    user = make_test_user()
    db.add(user)
    await db.flush()

    return user, org.id


async def _seed_second_org(db: AsyncSession) -> uuid.UUID:
    org_id = uuid.uuid4()
    db.add(
        Organization(
            id=org_id,
            name="Other Corp",
            slug="other-corp",
            status=OrganizationStatus.ACTIVE,
            is_platform=False,
        )
    )
    await db.flush()
    return org_id


async def _make_document(
    db: AsyncSession,
    user: User,
    org_id: uuid.UUID,
    filename: str = "hazard-log.pdf",
    folder_path: str | None = None,
) -> Document:
    repo = DocumentRepository(db)
    return await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename=filename,
        blob_path=f"{org_id}/{uuid.uuid4()}/{filename}",
        content_type="application/pdf",
        size_bytes=1024,
        folder_path=folder_path,
    )


# --- Folder creation ---


@pytest.mark.asyncio
async def test_create_folder_at_root(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Safety Reports")

    assert folder.name == "Safety Reports"
    assert folder.parent_id is None
    assert folder.organization_id == org_id


@pytest.mark.asyncio
async def test_create_folder_trims_whitespace(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "  Audits  ")

    assert folder.name == "Audits"


@pytest.mark.asyncio
async def test_create_nested_folder(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    parent = await service.create_folder(org_id, user.id, "PHL")
    child = await service.create_folder(org_id, user.id, "2026", parent_id=parent.id)

    assert child.parent_id == parent.id


@pytest.mark.asyncio
async def test_create_folder_rejects_empty_name(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    with pytest.raises(ValidationError, match="cannot be empty"):
        await service.create_folder(org_id, user.id, "   ")


@pytest.mark.asyncio
async def test_create_folder_rejects_path_separators(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    with pytest.raises(ValidationError, match="path separators"):
        await service.create_folder(org_id, user.id, "PHL/2026")


@pytest.mark.asyncio
async def test_create_folder_rejects_duplicate_sibling_name(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    await service.create_folder(org_id, user.id, "Audits")

    # Case-insensitive: "audits" reads as the same folder to a user scanning the tree.
    with pytest.raises(ConflictError, match="already exists"):
        await service.create_folder(org_id, user.id, "audits")


@pytest.mark.asyncio
async def test_same_name_allowed_under_different_parents(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    phl = await service.create_folder(org_id, user.id, "PHL")
    dca = await service.create_folder(org_id, user.id, "DCA")

    await service.create_folder(org_id, user.id, "2026", parent_id=phl.id)
    sibling = await service.create_folder(org_id, user.id, "2026", parent_id=dca.id)

    assert sibling.parent_id == dca.id


@pytest.mark.asyncio
async def test_create_folder_enforces_depth_limit(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    parent_id: uuid.UUID | None = None
    for level in range(MAX_FOLDER_DEPTH):
        folder = await service.create_folder(
            org_id, user.id, f"level-{level}", parent_id=parent_id
        )
        parent_id = folder.id

    with pytest.raises(ValidationError, match="nested more than"):
        await service.create_folder(org_id, user.id, "too-deep", parent_id=parent_id)


@pytest.mark.asyncio
async def test_create_folder_rejects_parent_from_another_org(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    other_org_id = await _seed_second_org(db_session)
    service = DocumentFolderService(db_session)

    foreign = await service.create_folder(other_org_id, user.id, "Theirs")

    with pytest.raises(NotFoundError):
        await service.create_folder(org_id, user.id, "Mine", parent_id=foreign.id)


# --- Rename and reparent ---


@pytest.mark.asyncio
async def test_rename_folder(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Untitled")
    renamed = await service.rename_folder(folder.id, org_id, "Safety Risk Assessments")

    assert renamed.name == "Safety Risk Assessments"


@pytest.mark.asyncio
async def test_rename_folder_rejects_sibling_clash(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    await service.create_folder(org_id, user.id, "Audits")
    other = await service.create_folder(org_id, user.id, "Reports")

    with pytest.raises(ConflictError):
        await service.rename_folder(other.id, org_id, "Audits")


@pytest.mark.asyncio
async def test_rename_folder_to_its_own_name_is_allowed(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Audits")
    renamed = await service.rename_folder(folder.id, org_id, "Audits")

    assert renamed.name == "Audits"


@pytest.mark.asyncio
async def test_move_folder_into_another(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    parent = await service.create_folder(org_id, user.id, "PHL")
    child = await service.create_folder(org_id, user.id, "2026")

    moved = await service.move_folder(child.id, org_id, parent.id)

    assert moved.parent_id == parent.id


@pytest.mark.asyncio
async def test_move_folder_to_root(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    parent = await service.create_folder(org_id, user.id, "PHL")
    child = await service.create_folder(org_id, user.id, "2026", parent_id=parent.id)

    moved = await service.move_folder(child.id, org_id, None)

    assert moved.parent_id is None


@pytest.mark.asyncio
async def test_move_folder_into_itself_is_rejected(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "PHL")

    with pytest.raises(ValidationError, match="into itself"):
        await service.move_folder(folder.id, org_id, folder.id)


@pytest.mark.asyncio
async def test_move_folder_into_own_descendant_is_rejected(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    grandparent = await service.create_folder(org_id, user.id, "Airports")
    parent = await service.create_folder(
        org_id, user.id, "PHL", parent_id=grandparent.id
    )
    child = await service.create_folder(org_id, user.id, "2026", parent_id=parent.id)

    with pytest.raises(ValidationError, match="own subfolders"):
        await service.move_folder(grandparent.id, org_id, child.id)


# --- Deletion ---


@pytest.mark.asyncio
async def test_delete_folder_unfiles_documents_without_deleting_them(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Audits")
    document = await _make_document(db_session, user, org_id)
    await service.move_documents([document.id], folder.id, org_id)

    await service.delete_folder(folder.id, org_id)
    db_session.expire_all()

    surviving = (
        await db_session.execute(select(Document).where(Document.id == document.id))
    ).scalar_one()
    assert surviving.folder_id is None


@pytest.mark.asyncio
async def test_delete_folder_removes_subfolders(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    parent = await service.create_folder(org_id, user.id, "Airports")
    child = await service.create_folder(org_id, user.id, "PHL", parent_id=parent.id)

    await service.delete_folder(parent.id, org_id)
    db_session.expire_all()

    remaining = (
        await db_session.execute(
            select(DocumentFolder).where(DocumentFolder.id == child.id)
        )
    ).scalar_one_or_none()
    assert remaining is None


@pytest.mark.asyncio
async def test_delete_folder_from_another_org_is_rejected(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    other_org_id = await _seed_second_org(db_session)
    service = DocumentFolderService(db_session)

    foreign = await service.create_folder(other_org_id, user.id, "Theirs")

    with pytest.raises(NotFoundError):
        await service.delete_folder(foreign.id, org_id)


# --- Moving documents ---


@pytest.mark.asyncio
async def test_move_documents_into_folder(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Audits")
    first = await _make_document(db_session, user, org_id, "a.pdf")
    second = await _make_document(db_session, user, org_id, "b.pdf")

    moved = await service.move_documents([first.id, second.id], folder.id, org_id)
    db_session.expire_all()

    assert moved == 2
    rows = (
        await db_session.execute(
            select(Document).where(Document.id.in_([first.id, second.id]))
        )
    ).scalars()
    assert all(row.folder_id == folder.id for row in rows)


@pytest.mark.asyncio
async def test_move_documents_to_root(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Audits")
    document = await _make_document(db_session, user, org_id)
    await service.move_documents([document.id], folder.id, org_id)

    await service.move_documents([document.id], None, org_id)
    db_session.expire_all()

    unfiled = (
        await db_session.execute(select(Document).where(Document.id == document.id))
    ).scalar_one()
    assert unfiled.folder_id is None


@pytest.mark.asyncio
async def test_move_documents_preserves_sharepoint_folder_path(
    db_session: AsyncSession,
) -> None:
    """The SharePoint mirror path is the dedup key for syncs, so a move must not touch it."""
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "My Working Set")
    document = await _make_document(
        db_session, user, org_id, folder_path="Airports/PHL/Safety"
    )

    await service.move_documents([document.id], folder.id, org_id)
    db_session.expire_all()

    moved = (
        await db_session.execute(select(Document).where(Document.id == document.id))
    ).scalar_one()
    assert moved.folder_path == "Airports/PHL/Safety"
    assert moved.folder_id == folder.id


@pytest.mark.asyncio
async def test_move_documents_rejects_empty_list(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Audits")

    with pytest.raises(ValidationError, match="No documents"):
        await service.move_documents([], folder.id, org_id)


@pytest.mark.asyncio
async def test_move_documents_rejects_unknown_document(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    service = DocumentFolderService(db_session)

    folder = await service.create_folder(org_id, user.id, "Audits")

    with pytest.raises(NotFoundError):
        await service.move_documents([uuid.uuid4()], folder.id, org_id)


@pytest.mark.asyncio
async def test_move_documents_rejects_folder_from_another_org(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    other_org_id = await _seed_second_org(db_session)
    service = DocumentFolderService(db_session)

    foreign = await service.create_folder(other_org_id, user.id, "Theirs")
    document = await _make_document(db_session, user, org_id)

    with pytest.raises(NotFoundError):
        await service.move_documents([document.id], foreign.id, org_id)


@pytest.mark.asyncio
async def test_list_folders_is_scoped_to_the_organization(
    db_session: AsyncSession,
) -> None:
    user, org_id = await _seed(db_session)
    other_org_id = await _seed_second_org(db_session)
    service = DocumentFolderService(db_session)

    await service.create_folder(org_id, user.id, "Mine")
    await service.create_folder(other_org_id, user.id, "Theirs")

    folders = await service.list_folders(org_id)

    assert [f.name for f in folders] == ["Mine"]
