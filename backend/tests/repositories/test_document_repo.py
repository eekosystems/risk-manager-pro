"""Tests for document repository."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentStatus
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.repositories.document import DocumentRepository
from tests.conftest import make_test_organization, make_test_user


async def _seed(db: AsyncSession) -> tuple[User, uuid.UUID]:
    """Seed a user and organization, return (user, organization_id)."""
    org = make_test_organization()
    db.add(org)
    await db.flush()

    user = make_test_user()
    db.add(user)
    await db.flush()

    return user, org.id


async def _seed_two_orgs(db: AsyncSession) -> tuple[User, uuid.UUID, uuid.UUID]:
    """Seed a user and two organizations, return (user, org_a_id, org_b_id)."""
    org_a = make_test_organization()
    db.add(org_a)
    await db.flush()

    org_b_id = uuid.uuid4()
    org_b = Organization(
        id=org_b_id,
        name="Other Corp",
        slug="other-corp",
        status=OrganizationStatus.ACTIVE,
        is_platform=False,
    )
    db.add(org_b)
    await db.flush()

    user = make_test_user()
    db.add(user)
    await db.flush()

    return user, org_a.id, org_b_id


@pytest.mark.asyncio
async def test_create_document(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="safety-manual.pdf",
        blob_path=f"{org_id}/{uuid.uuid4()}/safety-manual.pdf",
        content_type="application/pdf",
        size_bytes=2048,
    )

    assert doc.id is not None
    assert doc.filename == "safety-manual.pdf"
    assert doc.status == DocumentStatus.UPLOADED
    assert doc.organization_id == org_id


@pytest.mark.asyncio
async def test_get_by_id(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = DocumentRepository(db_session)

    created = await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="test.pdf",
        blob_path="path/to/test.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )

    fetched = await repo.get_by_id(created.id, org_id)
    assert fetched is not None
    assert fetched.id == created.id


@pytest.mark.asyncio
async def test_organization_isolation(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="secret.pdf",
        blob_path="path/to/secret.pdf",
        content_type="application/pdf",
        size_bytes=512,
    )

    other_org = uuid.uuid4()
    fetched = await repo.get_by_id(doc.id, other_org)
    assert fetched is None


@pytest.mark.asyncio
async def test_list_for_organization(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = DocumentRepository(db_session)

    await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="doc1.pdf",
        blob_path="p/d/doc1.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )
    await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="doc2.txt",
        blob_path="p/d/doc2.txt",
        content_type="text/plain",
        size_bytes=200,
    )

    docs, total = await repo.list_for_organization(org_id)
    assert total == 2
    assert len(docs) == 2


@pytest.mark.asyncio
async def test_update_status(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="processing.pdf",
        blob_path="p/d/processing.pdf",
        content_type="application/pdf",
        size_bytes=300,
    )

    await repo.update_status(doc.id, DocumentStatus.INDEXED, chunk_count=10)

    updated = await repo.get_by_id(doc.id, org_id)
    assert updated is not None
    assert updated.status == DocumentStatus.INDEXED
    assert updated.chunk_count == 10


@pytest.mark.asyncio
async def test_delete_document(db_session: AsyncSession) -> None:
    user, org_id = await _seed(db_session)
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="delete-me.pdf",
        blob_path="p/d/delete-me.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )

    result = await repo.delete(doc.id, org_id)
    assert result is True

    fetched = await repo.get_by_id(doc.id, org_id)
    assert fetched is None


# --- Tenant Isolation Tests ---


@pytest.mark.asyncio
async def test_update_status_with_org_isolation(db_session: AsyncSession) -> None:
    """update_status with org_id should only update if org matches."""
    user, org_a, org_b = await _seed_two_orgs(db_session)
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        organization_id=org_a,
        uploaded_by=user.id,
        filename="org-a-doc.pdf",
        blob_path="p/d/org-a-doc.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )

    # Should succeed with matching org
    await repo.update_status(
        doc.id, DocumentStatus.INDEXED, chunk_count=5, organization_id=org_a
    )
    updated = await repo.get_by_id(doc.id, org_a)
    assert updated is not None
    assert updated.status == DocumentStatus.INDEXED

    # Should be no-op with wrong org
    await repo.update_status(
        doc.id, DocumentStatus.FAILED, error_message="hack", organization_id=org_b
    )
    still_indexed = await repo.get_by_id(doc.id, org_a)
    assert still_indexed is not None
    assert still_indexed.status == DocumentStatus.INDEXED


@pytest.mark.asyncio
async def test_list_org_a_invisible_from_org_b(db_session: AsyncSession) -> None:
    """Documents created in Org A should not appear in Org B listing."""
    user, org_a, org_b = await _seed_two_orgs(db_session)
    repo = DocumentRepository(db_session)

    await repo.create(
        organization_id=org_a,
        uploaded_by=user.id,
        filename="a-doc.pdf",
        blob_path="p/d/a-doc.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )

    docs_b, total_b = await repo.list_for_organization(org_b)
    assert total_b == 0
    assert len(docs_b) == 0


@pytest.mark.asyncio
async def test_delete_org_isolation(db_session: AsyncSession) -> None:
    """Cannot delete a document using the wrong org_id."""
    user, org_a, org_b = await _seed_two_orgs(db_session)
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        organization_id=org_a,
        uploaded_by=user.id,
        filename="protected.pdf",
        blob_path="p/d/protected.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )

    # Delete with wrong org should fail
    result = await repo.delete(doc.id, org_b)
    assert result is False

    # Document should still exist
    fetched = await repo.get_by_id(doc.id, org_a)
    assert fetched is not None


@pytest.mark.asyncio
async def test_get_by_id_system_bypasses_org(db_session: AsyncSession) -> None:
    """get_by_id_system should return document regardless of org."""
    user, org_id = await _seed(db_session)
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        organization_id=org_id,
        uploaded_by=user.id,
        filename="system-doc.pdf",
        blob_path="p/d/system-doc.pdf",
        content_type="application/pdf",
        size_bytes=100,
    )

    fetched = await repo.get_by_id_system(doc.id)
    assert fetched is not None
    assert fetched.id == doc.id
