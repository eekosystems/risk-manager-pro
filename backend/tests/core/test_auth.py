"""Tests for auth token validation."""

import uuid
from unittest.mock import patch

import jwt
import pytest

from app.core.auth import EntraIDAuth, TokenPayload
from app.core.exceptions import UnauthorizedError

# RSA key pair for testing (generated with cryptography library — test only)
TEST_KID = "test-kid-001"
TEST_PRIVATE_KEY = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEAorMGcEjlsMAoFofg092DfjgEgiH3m6WOWhPDHn9mYVLil/Mr\n"
    "3N8WHVTtDLreXco/Sio2VnhYd+RXHFgqKBmPiFu2aQDD1kagPtTKoSx/gA8+YE5m\n"
    "Kf5hqtXZiOFx/lkyts0Zeyj/ej8Apc2vvVRXafHQwin2a8noRj7Nm7waF/xmSDvt\n"
    "EXtpaUhZK4ykHPDkSRSD8PYJe8uIT5Xw1Q7/g+nPRRyvYzHokmww/s+9/oW+aqfA\n"
    "e6jgkar7pSqc7RjcVh702ZIDGQD87OOm/lN3CVYTrXDDK92E1Vz2PCUr+KUfA48P\n"
    "+3k5Re7HUt+3Rn/YoIdFKkZltCBnajgb9n3REQIDAQABAoIBAARsIBLNgnPKV1Sc\n"
    "cyWjHePAh0vXu0SfbIYBh0JVFW30DC1z6kdtx2q68BoSWsC7InsEOHejfAkfO2ht\n"
    "c5DlN/ftgUDrqMcSYqDulQbqQBl1oJ0KyH9f9xznBOuR8DCpEUYzfzuwJriWjZCU\n"
    "LZCUgi9Cp8ldTWHK6k29f4Z6B44LDs7o1yLPnLMI9aGufMO48mC/XGkoxETmkwQq\n"
    "oy6rK7FzSiUwD1o/iwfSd1c0lwM8VWLewem+LAskh1LRnGCwB2tb0l2c1DuXfKrC\n"
    "dod8J6ugO15Za6MKs8/qi6IvjL3M+5j7pbuc/PeOqAL0g+zc9jck6Dwy00MhwK8s\n"
    "IzplA7kCgYEAzFCvq65bsnrD3BvFwUdMu37wALEj0uau3eEYBu3zMFb2rWpScyTf\n"
    "0oaYmvfZVZJ4B/voD+z1VKOd3KOglpaEyjBI+1vAUdfY65JEouGe9z8WQVnX0tEe\n"
    "SFZwpg97vS8DFgW61Ik3faEHHUXQiR5vTd4lOpIaX9uqHcLFNWalNxkCgYEAy9tS\n"
    "1ki8TV/GA5I2O4bgTiBHqauvciTTYs/VL1MAYXRElWsGzY+fBTKcSdrILI5sE32x\n"
    "HctaNUgqHor9DcAOcR6rbCCBgcUfMUage8aGYdJ9ngpoa8nEfBaJ7+RZinkfojVa\n"
    "+4McYAFK0FDHRWIMr7/L6ySRMyNZsrLGCGIBALkCgYACvlKdi4nPq7ZVjknpfnuZ\n"
    "SOsQF1DT1CUk9ZDNBwTs8T3+th7FTQl0WjpSWmGgtIbIFKnZDOV+bXQBMnFFlF/U\n"
    "FzHjrie28Z8ICr7BMSZhS4eQ+RPc0NIHRqHcmPigYbE46nrHv8/u7+qYigdyz+XO\n"
    "tdzqHGwePWTbYXIkdWxigQKBgDjWDWJxJQ7thOe5/CTcle0yUsibdW79lXIXP/jR\n"
    "y2lgYT7HeD4XrN5mHez5cpX5n2hPwvHroFr6o8OgPK14vo4LXv/mkDT+IJQ8fMIF\n"
    "t7HOXfeSL0reFkoCfrLDl7Nj0c4H0jYNd/vMYG90FhriG2dkshX9O/5l/Lw128C6\n"
    "kk0BAoGBAJ6iPHcm7QA/GquAaLFfbQCRj7hrKmPdy/zyKaKeQnTsQhmTDCbcefb4\n"
    "mYIWkG+732lUTZtxqO5vbZX06rlFFjKgdr4u0/vOJ+5cs+mbjTBpgYTrFg2DMbJV\n"
    "FO6wNFCltsjspqRSJcXusYnKIPeKfFPSWxz0QYSTxHgVeohDRC+a\n"
    "-----END RSA PRIVATE KEY-----\n"
)

TEST_PUBLIC_KEY_JWK = {
    "kid": TEST_KID,
    "kty": "RSA",
    "alg": "RS256",
    "use": "sig",
    "n": "orMGcEjlsMAoFofg092DfjgEgiH3m6WOWhPDHn9mYVLil_Mr3N8WHVTtDLreXco_Sio2VnhYd-RXHFgqKBmPiFu2aQDD1kagPtTKoSx_gA8-YE5mKf5hqtXZiOFx_lkyts0Zeyj_ej8Apc2vvVRXafHQwin2a8noRj7Nm7waF_xmSDvtEXtpaUhZK4ykHPDkSRSD8PYJe8uIT5Xw1Q7_g-nPRRyvYzHokmww_s-9_oW-aqfAe6jgkar7pSqc7RjcVh702ZIDGQD87OOm_lN3CVYTrXDDK92E1Vz2PCUr-KUfA48P-3k5Re7HUt-3Rn_YoIdFKkZltCBnajgb9n3REQ",
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
