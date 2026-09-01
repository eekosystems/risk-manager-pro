import time
import uuid
from datetime import datetime, timedelta

import structlog
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenPayload, entra_auth
from app.core.auth_throttle import auth_throttle
from app.core.config import settings
from app.core.database import get_db
from app.core.deps.common import get_audit_logger
from app.core.exceptions import ForbiddenError, TooManyRequestsError, UnauthorizedError
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User

logger = structlog.get_logger(__name__)

LAST_LOGIN_THROTTLE = timedelta(seconds=settings.last_login_throttle_seconds)
LAST_ACTIVITY_THROTTLE = timedelta(seconds=settings.last_activity_throttle_seconds)
SESSION_TIMEOUT = timedelta(minutes=settings.session_timeout_minutes)


async def get_token_payload(request: Request) -> TokenPayload:
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")[:500]
    correlation_id = getattr(request.state, "correlation_id", "")

    # Check if IP is locked out due to repeated auth failures
    if auth_throttle.is_locked_out(client_ip):
        logger.warning(
            "auth_lockout",
            reason="too_many_failures",
            client_ip=client_ip,
            correlation_id=correlation_id,
        )
        raise TooManyRequestsError("Too many failed authentication attempts. Try again later.")

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        auth_throttle.record_failure(client_ip)
        logger.warning(
            "auth_failure",
            reason="missing_authorization_header",
            client_ip=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = await entra_auth.validate_token(
            token,
            client_ip=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )
    except UnauthorizedError:
        auth_throttle.record_failure(client_ip)
        raise

    # Successful auth — clear any failure history for this IP
    auth_throttle.record_success(client_ip)
    return payload


def _is_bootstrap_platform_admin(email: str) -> bool:
    return bool(email) and email.strip().lower() in settings.platform_admin_email_set


async def _apply_platform_admin_bootstrap(db: AsyncSession, user: User) -> None:
    """Grant platform administration to addresses named in configuration.

    Grant-only. An address removed from the setting keeps whatever access it
    has, so this never fights the in-app toggle or silently demotes anyone.
    """
    if user.is_platform_admin or not _is_bootstrap_platform_admin(user.email):
        return
    user.is_platform_admin = True
    await db.flush()
    logger.info("platform_admin_bootstrapped", user_id=str(user.id))


async def _get_or_create_user(db: AsyncSession, token: TokenPayload, request: Request) -> User:
    """Look up an existing user by Entra ID or auto-provision a new one."""
    stmt = select(User).where(User.entra_id == token.oid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        await _apply_platform_admin_bootstrap(db, user)
        return user

    user = User(
        entra_id=token.oid,
        email=token.preferred_username or f"{token.oid}@unknown",
        display_name=token.name or "Unknown User",
        is_platform_admin=_is_bootstrap_platform_admin(token.preferred_username or ""),
    )
    db.add(user)
    await db.flush()

    org = await _get_or_create_org_for_tenant(db, token.tid, request)
    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role=MembershipRole.VIEWER,
    )
    db.add(membership)
    await db.flush()

    logger.info("user_auto_provisioned", user_id=str(user.id), org_id=str(org.id))

    # Audit log for auto-provisioning
    audit = await get_audit_logger(request)
    await audit.log(
        action="user.auto_provisioned",
        user=user,
        resource_type="user",
        resource_id=str(user.id),
        organization_id=org.id,
    )

    return user


async def _enforce_session_timeout(
    db: AsyncSession, user: User, token: TokenPayload, now: datetime
) -> bool:
    """Enforce the idle-session timeout (60 min of inactivity, CC6.1).

    Returns True if the session was re-established from a genuine re-auth
    (caller should treat the request as the start of a fresh session).
    Raises UnauthorizedError if the session has been idle past the timeout and
    the presented token is not itself fresh — i.e. no real re-authentication
    happened, so a stale/replayed token must not be admitted.
    """
    if user.last_activity is None or (now - user.last_activity) <= SESSION_TIMEOUT:
        return False

    # Idle past the timeout. Admit the request only if the bearer token was
    # minted within the timeout window, which proves the caller just
    # re-authenticated (interactive sign-in or MSAL silent refresh). The token's
    # iat is the session clock; a token older than the window cannot revive an
    # idle session.
    token_age_seconds = time.time() - token.iat if token.iat else None
    if token_age_seconds is not None and token_age_seconds <= SESSION_TIMEOUT.total_seconds():
        logger.info(
            "session_reestablished",
            user_id=str(user.id),
            last_activity=user.last_activity.isoformat(),
        )
        user.last_activity = now
        user.last_login = now
        await db.flush()
        return True

    logger.warning(
        "session_expired",
        user_id=str(user.id),
        last_activity=user.last_activity.isoformat(),
    )
    raise UnauthorizedError("Session expired due to inactivity. Please sign in again.")


async def _update_activity_timestamps(db: AsyncSession, user: User, now: datetime) -> None:
    """Throttled updates to last_login and last_activity to reduce DB writes."""
    # Update last_login (throttled)
    if user.last_login is None or (now - user.last_login) > LAST_LOGIN_THROTTLE:
        user.last_login = now
        await db.flush()

    # Update last_activity (throttled to reduce DB writes)
    if user.last_activity is None or (now - user.last_activity) > LAST_ACTIVITY_THROTTLE:
        user.last_activity = now
        await db.flush()


async def get_current_user(
    request: Request,
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _get_or_create_user(db, token, request)

    if not user.is_active:
        raise ForbiddenError("User account is deactivated")

    now = datetime.utcnow()

    # Enforce idle-session timeout. Rejects (401) when the session has been idle
    # past the window and the token is not freshly minted; admits and resets the
    # clock when the request carries a fresh re-auth token.
    if await _enforce_session_timeout(db, user, token, now):
        return user

    await _update_activity_timestamps(db, user, now)

    return user


async def _get_or_create_org_for_tenant(
    db: AsyncSession, azure_tenant_id: str, request: Request | None = None
) -> Organization:
    # Never silently provision an organization for an unrecognised tenant.
    # validate_token already rejects foreign tenants, so in production this is a
    # defence-in-depth assertion; in dev (no tenant configured) it is skipped.
    configured_tenant = settings.azure_ad_tenant_id
    if configured_tenant and azure_tenant_id != configured_tenant:
        logger.warning("org_autocreate_blocked", token_tenant=azure_tenant_id)
        raise ForbiddenError("Tenant is not provisioned for this application")

    if not azure_tenant_id:
        azure_tenant_id = str(uuid.uuid4())

    org_id = (
        uuid.UUID(azure_tenant_id)
        if len(azure_tenant_id) == 36
        else uuid.uuid5(uuid.NAMESPACE_URL, azure_tenant_id)
    )

    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if org is None:
        slug = f"org-{str(org_id)[:8]}"
        org = Organization(
            id=org_id,
            name=f"Organization {str(org_id)[:8]}",
            slug=slug,
            status=OrganizationStatus.ACTIVE,
        )
        db.add(org)
        await db.flush()
        logger.info("organization_auto_created", org_id=str(org_id))

    return org
