"""Per-account SharePoint folder scoping.

Document rows were already isolated by organization_id, so one account could
not read another's data. These cover the other half: what an account is
allowed to pull out of the shared SharePoint library in the first place.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.services.folder_scope import (
    MAX_SCOPES_PER_ORGANIZATION,
    FolderScopeService,
    path_is_within,
)
from tests.conftest import make_test_user

ROOT = "RMP Master Directory/Airport - Safety Risk Management Documents"
SEATTLE = f"{ROOT}/SEA"
PORTLAND = f"{ROOT}/PDX"


@pytest.fixture(autouse=True)
def _airport_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sharepoint_airport_root_folder", ROOT)


async def _seed_user(db: AsyncSession) -> User:
    user = make_test_user()
    db.add(user)
    await db.flush()
    return user


async def _seed_org(
    db: AsyncSession, *, is_platform: bool = False, slug: str = "seattle"
) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        name=slug.upper(),
        slug=slug,
        status=OrganizationStatus.ACTIVE,
        is_platform=is_platform,
    )
    db.add(org)
    await db.flush()
    return org


# --- Path containment ---


def test_path_is_within_matches_the_root_itself() -> None:
    assert path_is_within(SEATTLE, SEATTLE) is True


def test_path_is_within_matches_a_descendant() -> None:
    assert path_is_within(f"{SEATTLE}/2026/Audits", SEATTLE) is True


def test_path_is_within_rejects_a_sibling() -> None:
    assert path_is_within(PORTLAND, SEATTLE) is False


def test_path_is_within_rejects_a_prefix_collision() -> None:
    # "SEA-Cargo" starts with "SEA" as a string but is a different folder.
    assert path_is_within(f"{ROOT}/SEA-Cargo", SEATTLE) is False


def test_path_is_within_rejects_traversal() -> None:
    assert path_is_within(f"{SEATTLE}/../PDX", SEATTLE) is False


# --- Assigning scopes ---


@pytest.mark.asyncio
async def test_set_and_list_scopes(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)

    stored = await service.set_paths(org.id, [SEATTLE, PORTLAND], user.id)

    assert stored == [SEATTLE, PORTLAND]
    assert sorted(await service.list_paths(org.id)) == sorted([SEATTLE, PORTLAND])


@pytest.mark.asyncio
async def test_setting_scopes_replaces_the_previous_set(
    db_session: AsyncSession,
) -> None:
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)
    await service.set_paths(org.id, [SEATTLE, PORTLAND], user.id)

    await service.set_paths(org.id, [SEATTLE], user.id)

    assert await service.list_paths(org.id) == [SEATTLE]


@pytest.mark.asyncio
async def test_scopes_are_deduplicated_and_normalized(
    db_session: AsyncSession,
) -> None:
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)

    stored = await service.set_paths(org.id, [f"/{SEATTLE}/", SEATTLE, "  " + SEATTLE], user.id)

    assert stored == [SEATTLE]


@pytest.mark.asyncio
async def test_a_scope_outside_the_airport_root_is_rejected(
    db_session: AsyncSession,
) -> None:
    """A scope must not be pointable at unrelated parts of the library."""
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)

    with pytest.raises(ValidationError, match="outside the permitted"):
        await service.set_paths(org.id, ["Confidential/Executive"], user.id)


@pytest.mark.asyncio
async def test_a_traversal_scope_is_rejected(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)

    with pytest.raises(ValidationError):
        await service.set_paths(org.id, [f"{ROOT}/../../Confidential"], user.id)


@pytest.mark.asyncio
async def test_too_many_scopes_are_rejected(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)
    paths = [f"{ROOT}/AP{i}" for i in range(MAX_SCOPES_PER_ORGANIZATION + 1)]

    with pytest.raises(ValidationError, match="more than"):
        await service.set_paths(org.id, paths, user.id)


# --- What an account may import ---


@pytest.mark.asyncio
async def test_an_unscoped_client_account_may_import_nothing(
    db_session: AsyncSession,
) -> None:
    """Fails closed: a new account imports nothing until it is granted a folder."""
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)

    assert await service.allowed_roots(org) == []
    assert await service.is_path_allowed(org, SEATTLE) is False
    assert await service.is_path_allowed(org, ROOT) is False


@pytest.mark.asyncio
async def test_the_platform_account_still_imports_everything(
    db_session: AsyncSession,
) -> None:
    """Faith Group's own account keeps crawling the whole library as before."""
    org = await _seed_org(db_session, is_platform=True, slug="faith-group")
    service = FolderScopeService(db_session)

    assert await service.allowed_roots(org) is None
    assert await service.is_path_allowed(org, SEATTLE) is True


@pytest.mark.asyncio
async def test_a_scoped_account_reaches_only_its_own_folder(
    db_session: AsyncSession,
) -> None:
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)
    await service.set_paths(org.id, [SEATTLE], user.id)

    assert await service.is_path_allowed(org, SEATTLE) is True
    assert await service.is_path_allowed(org, f"{SEATTLE}/2026") is True
    # The whole point: Seattle cannot reach Portland, or the shared parent.
    assert await service.is_path_allowed(org, PORTLAND) is False
    assert await service.is_path_allowed(org, ROOT) is False


@pytest.mark.asyncio
async def test_a_scoped_account_cannot_escape_by_traversal(
    db_session: AsyncSession,
) -> None:
    user = await _seed_user(db_session)
    org = await _seed_org(db_session)
    service = FolderScopeService(db_session)
    await service.set_paths(org.id, [SEATTLE], user.id)

    assert await service.is_path_allowed(org, f"{SEATTLE}/../PDX") is False


@pytest.mark.asyncio
async def test_scoping_a_platform_account_restricts_it(
    db_session: AsyncSession,
) -> None:
    """An explicit scope wins over the platform account's blanket access."""
    user = await _seed_user(db_session)
    org = await _seed_org(db_session, is_platform=True, slug="faith-group")
    service = FolderScopeService(db_session)
    await service.set_paths(org.id, [SEATTLE], user.id)

    assert await service.allowed_roots(org) == [SEATTLE]
    assert await service.is_path_allowed(org, PORTLAND) is False


@pytest.mark.asyncio
async def test_scopes_do_not_leak_between_accounts(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    seattle = await _seed_org(db_session, slug="seattle")
    portland = await _seed_org(db_session, slug="portland")
    service = FolderScopeService(db_session)

    await service.set_paths(seattle.id, [SEATTLE], user.id)
    await service.set_paths(portland.id, [PORTLAND], user.id)

    assert await service.is_path_allowed(seattle, PORTLAND) is False
    assert await service.is_path_allowed(portland, SEATTLE) is False
