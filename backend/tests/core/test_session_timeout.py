"""Tests for idle-session timeout enforcement (CC6.1)."""

import time
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.auth import TokenPayload
from app.core.deps.auth import SESSION_TIMEOUT, _enforce_session_timeout
from app.core.exceptions import UnauthorizedError


def _user(last_activity: datetime | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        last_activity=last_activity,
        last_login=last_activity,
    )


def _token(iat: int) -> TokenPayload:
    return TokenPayload(sub="s", oid="o", tid="t", iat=iat)


@pytest.mark.asyncio
async def test_no_prior_activity_does_not_trigger() -> None:
    db = AsyncMock()
    now = datetime.utcnow()
    user = _user(None)

    renewed = await _enforce_session_timeout(db, user, _token(int(time.time())), now)

    assert renewed is False
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_recent_activity_does_not_trigger() -> None:
    db = AsyncMock()
    now = datetime.utcnow()
    user = _user(now - timedelta(minutes=1))

    renewed = await _enforce_session_timeout(db, user, _token(int(time.time())), now)

    assert renewed is False
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_idle_with_fresh_token_reestablishes_session() -> None:
    db = AsyncMock()
    now = datetime.utcnow()
    user = _user(now - SESSION_TIMEOUT - timedelta(minutes=5))

    # Token minted just now → genuine re-auth → session re-established.
    renewed = await _enforce_session_timeout(db, user, _token(int(time.time())), now)

    assert renewed is True
    assert user.last_activity == now
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_idle_with_stale_token_rejected() -> None:
    db = AsyncMock()
    now = datetime.utcnow()
    user = _user(now - SESSION_TIMEOUT - timedelta(minutes=5))

    # Token minted well outside the window → no real re-auth → reject.
    stale_iat = int(time.time()) - int(SESSION_TIMEOUT.total_seconds()) - 600

    with pytest.raises(UnauthorizedError, match="Session expired"):
        await _enforce_session_timeout(db, user, _token(stale_iat), now)
