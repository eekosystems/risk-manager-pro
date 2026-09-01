"""Granting platform administration from configuration.

is_platform_admin is a database column that nothing in the sign-in path ever
set, so a fresh deployment had no platform admin and no way to make one
through the app. These cover the configured bootstrap that closes that.
"""

import pytest

from app.core.config import settings
from app.core.deps.auth import _is_bootstrap_platform_admin


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "platform_admin_emails", "admin@faithgroupllc.com, second@fg.com")


def test_a_configured_address_is_a_platform_admin(configured: None) -> None:
    assert _is_bootstrap_platform_admin("admin@faithgroupllc.com") is True


def test_matching_ignores_case(configured: None) -> None:
    """Entra hands back whatever casing the directory holds."""
    assert _is_bootstrap_platform_admin("Admin@FaithGroupLLC.com") is True


def test_matching_ignores_surrounding_whitespace(configured: None) -> None:
    assert _is_bootstrap_platform_admin("  second@fg.com  ") is True


def test_an_unlisted_address_is_not_an_admin(configured: None) -> None:
    assert _is_bootstrap_platform_admin("analyst@seattleairport.org") is False


def test_an_empty_address_is_not_an_admin(configured: None) -> None:
    assert _is_bootstrap_platform_admin("") is False


def test_nobody_is_an_admin_when_the_setting_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default must not hand anyone platform access."""
    monkeypatch.setattr(settings, "platform_admin_emails", "")

    assert _is_bootstrap_platform_admin("admin@faithgroupllc.com") is False


def test_a_partial_address_does_not_match(configured: None) -> None:
    # Guards against substring matching, which would let
    # "evil-admin@faithgroupllc.com.attacker.test" through.
    assert _is_bootstrap_platform_admin("admin@faithgroupllc.com.attacker.test") is False
    assert _is_bootstrap_platform_admin("faithgroupllc.com") is False


def test_the_setting_tolerates_ragged_formatting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "platform_admin_emails", " a@b.com ,, c@d.com,  , e@f.com ")

    assert settings.platform_admin_email_set == frozenset({"a@b.com", "c@d.com", "e@f.com"})
