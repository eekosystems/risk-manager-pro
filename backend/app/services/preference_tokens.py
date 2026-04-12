import base64
import hashlib
import hmac
import json
import time
import uuid

from app.core.config import settings

_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 90  # 90 days


def _secret_bytes() -> bytes:
    secret = settings.qaqc_preference_token_secret
    if not secret:
        raise RuntimeError("QAQC_PREFERENCE_TOKEN_SECRET is not configured")
    return secret.encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_preference_token(user_id: uuid.UUID) -> str:
    """Issue a signed HMAC token that grants preference-change access for this user."""
    payload = {"uid": str(user_id), "iat": int(time.time())}
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_secret_bytes(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url(signature)}"


def verify_preference_token(token: str) -> uuid.UUID | None:
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(_secret_bytes(), body.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64url_decode(sig)
    except (ValueError, base64.binascii.Error):
        return None
    if not hmac.compare_digest(expected, provided):
        return None
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    issued_at = payload.get("iat")
    if not isinstance(issued_at, int) or time.time() - issued_at > _TOKEN_TTL_SECONDS:
        return None
    try:
        return uuid.UUID(payload["uid"])
    except (KeyError, ValueError):
        return None
