"""Tests for auth token validation."""

import uuid
from unittest.mock import patch

import jwt
import pytest

from app.core.auth import EntraIDAuth, TokenPayload
from app.core.exceptions import UnauthorizedError

# RSA key pair for testing (NOT a real key — test only)
TEST_KID = "test-kid-001"
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA2a2rwplBQXzOqkHLJNqMOEFolSJMUbGo38cGzRcmEMPOEOi8
6EMy7RCVfKqWCkaap6JhOjXObXN8W6RTK92n+eYJjSMo0+kUR6MFlVLEJV2X1eBb
YJJJOnEHG8eMP7llQAaJEYHp9YKNfn0/nqpvr5WLmYMDBL/c/Z2XigZ5moDb0RH5
2EMXhLLQlVvHJJZVprlGHc0ymO32Oy24CbzhLQxzC7yCmsbaF5B5MYKljcEfvYPJ
dVZ5sVBKdGvLxIMIR7dNqGkMCB9LmU+jGFGfTMPiE2C0V6bJMHGSP7MjBMnk6VNH
bHi83RNb9xs5XB4TRz6VXdb5f4YBRiG+dVn3NwIDAQABAoIBAC3kWiTKhMuxi0v3
6UkU2hKCd3tDqISmFqNAm/YDnFxHMFm4AoI/dA0ss9pVNJu3V6GKqWSp2dO5b0vL
9n8p5GpVXzkBE0ZwWMG2YDzR3JIQZVlVkaLBXP3T4wEFU3q3fPVU0lAQz0ScGJWq
ELJQpfMjOX5N+D3DVRC7Yf6RUpXgU1zJQMVt2k9zJ0stKmMvqz00K4c8hFzPKsCF
4Dxy6aGMXxjjz6VMsZ+r3YPnj3M6dVWHLaQ6QkPjMLxI/F+NU+/84J5b5bP7L6T/
mH0Yk4v2wVy69PLolTb5Y0Xpn6Y2ouFMC5C4BAmn7d8FgQEJlMnP3FowDP4G8ung
p8p2g0ECgYEA7V3GBfaGe6jEPlBCLU30OlDEbQHnIR0avHXQ2RJh5NoEyrLGOZM0
HiLGhwS/E0v/ooYdT0JDj0S2UqbfJtP9+rW1Kv7l9c4jFHq+HOjSfFh5Bm2cXjp
I/oFC/VN6T/VadNTwaR1IfyQN22/ZXHj7DF20p3l9oMCi4d9S5cQF0cCgYEA6kCR
n3A+Z8ZdNd/fai2bBV6/yT+gQTB0rNPqfL1pwkKHLLB1aaGJ0ViL2UBERsXlRD87
xF8j2FqlVJM9J2WJ0hGFxR1K8RW8P0JbcHQw7WBa0qlReXPW9gFD01w/6wnxfYME
jRbwXR5XHD0hWBxGm7V3S5+/QxS90KXBNlZLhYECgYEAiVPNmE6VXM0e7CW7iECF
JHxf5BoFlbE6LqB3NI7cRS5mJHqXI0C3wYKn9t7EKKI9J+ZcS1TAjKNveYm5YJtp
hUxbCvhFM5VNQBFfXOj8lFfqYuU6cL/IpxHUCEPOF3v8JA+1CLeNp2urhL8Cf4SQ
U5BXz0PmrI5KHjMHEPe6Nz8CgYAfW+YXn5aibFlAU9iM7fVICdNLPdz3GIV3FlrO
UPJ3MYeVUxk3WkWBFfUhA6ofRd7NxJqL0YDhMO3K11N2dEJLoCfBLtjG4zhsYe/O
sXkT5HlU5iQnXlDlE5eKJ+0nh9VHIXrY+1oQ/51c+QqrC9QBZ5R4x5DXaUjWGat
oQRfAQKBgQCDjWm/bD1AHO5S4IiSyIXVFKCnQXn5j0Lt1Z3FKFEjxMj1jJit+2Q9
H55cPcRY/xHLnj0PEfoe4laEr8+LNzSvvQfI6BwJNoHJkfaSE4Kj3dC/WLKhV/pv
j+ZJDuN0a+7Q4l6I5A5VJhKXGkLOGOYaf5Y/t/AxKsOPmmygjZx1Q==
-----END RSA PRIVATE KEY-----"""

TEST_PUBLIC_KEY_JWK = {
    "kid": TEST_KID,
    "kty": "RSA",
    "alg": "RS256",
    "use": "sig",
    "n": "2a2rwplBQXzOqkHLJNqMOEFolSJMUbGo38cGzRcmEMPOEOi86EMy7RCVfKqWCkaap6JhOjXObXN8W6RTK92n-eYJjSMo0-kUR6MFlVLEJV2X1eBbYJJJOnEHG8eMP7llQAaJEYHp9YKNfn0_nqpvr5WLmYMDBL_c_Z2XigZ5moDb0RH52EMXhLLQlVvHJJZVprlGHc0ymO32Oy24CbzhLQxzC7yCmsbaF5B5MYKljcEfvYPJdVZ5sVBKdGvLxIMIR7dNqGkMCB9LmU-jGFGfTMPiE2C0V6bJMHGSP7MjBMnk6VNHbHi83RNb9xs5XB4TRz6VXdb5f4YBRiG-dVn3Nw",
    "e": "AQAB",
}


def _make_token(
    claims: dict[str, object] | None = None,
    kid: str = TEST_KID,
    expired: bool = False,
) -> str:
    import time

    now = int(time.time())
    default_claims: dict[str, object] = {
        "sub": "user-sub-123",
        "oid": str(uuid.uuid4()),
        "tid": str(uuid.uuid4()),
        "preferred_username": "testuser@example.com",
        "name": "Test User",
        "roles": [],
        "aud": "",  # Will be overridden by settings
        "iss": "",
        "iat": now,
        "exp": now - 3600 if expired else now + 3600,
    }
    if claims:
        default_claims.update(claims)

    headers = {"kid": kid, "alg": "RS256"}
    return jwt.encode(default_claims, TEST_PRIVATE_KEY, algorithm="RS256", headers=headers)


@pytest.mark.asyncio
async def test_valid_jwt_returns_payload() -> None:
    auth = EntraIDAuth()

    with patch.object(auth, "_fetch_jwks") as mock_fetch:
        mock_fetch.return_value = None
        auth._jwks = {TEST_KID: TEST_PUBLIC_KEY_JWK}

        token = _make_token()

        # Bypass issuer/audience validation for unit test
        with patch("app.core.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-sub-123",
                "oid": "oid-123",
                "tid": "tid-123",
                "preferred_username": "test@example.com",
                "name": "Test User",
                "roles": ["analyst"],
            }
            result = await auth.validate_token(token)

    assert isinstance(result, TokenPayload)
    assert result.sub == "user-sub-123"
    assert result.oid == "oid-123"


@pytest.mark.asyncio
async def test_expired_token_raises_unauthorized() -> None:
    auth = EntraIDAuth()

    with patch.object(auth, "_fetch_jwks") as mock_fetch:
        mock_fetch.return_value = None
        auth._jwks = {TEST_KID: TEST_PUBLIC_KEY_JWK}

        token = _make_token(expired=True)

        with patch("app.core.auth.jwt.decode") as mock_decode:
            from jwt.exceptions import PyJWTError
            mock_decode.side_effect = PyJWTError("Token expired")

            with pytest.raises(UnauthorizedError):
                await auth.validate_token(token)


@pytest.mark.asyncio
async def test_wrong_audience_raises_unauthorized() -> None:
    auth = EntraIDAuth()

    with patch.object(auth, "_fetch_jwks") as mock_fetch:
        mock_fetch.return_value = None
        auth._jwks = {TEST_KID: TEST_PUBLIC_KEY_JWK}

        token = _make_token()

        with patch("app.core.auth.jwt.decode") as mock_decode:
            from jwt.exceptions import PyJWTError
            mock_decode.side_effect = PyJWTError("Invalid audience")

            with pytest.raises(UnauthorizedError):
                await auth.validate_token(token)


@pytest.mark.asyncio
async def test_unknown_kid_raises_unauthorized() -> None:
    auth = EntraIDAuth()

    with patch.object(auth, "_fetch_jwks") as mock_fetch:
        mock_fetch.return_value = None
        auth._jwks = {"some-other-kid": TEST_PUBLIC_KEY_JWK}

        token = _make_token(kid="unknown-kid")

        with pytest.raises(UnauthorizedError, match="signing key not found"):
            await auth.validate_token(token)
