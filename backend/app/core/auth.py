import time
from typing import TYPE_CHECKING, cast

import httpx
import jwt
import structlog
from jwt.exceptions import PyJWTError
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

logger = structlog.get_logger(__name__)

JWKS_CACHE_TTL_SECONDS = 86400  # 24 hours


class TokenPayload(BaseModel):
    sub: str
    oid: str
    tid: str
    preferred_username: str | None = None
    name: str | None = None
    roles: list[str] = []


class EntraIDAuth:
    def __init__(self) -> None:
        self._jwks: dict[str, dict[str, str]] = {}
        self._jwks_fetched_at: float = 0.0

    def _is_cache_stale(self) -> bool:
        if not self._jwks:
            return True
        return (time.monotonic() - self._jwks_fetched_at) > JWKS_CACHE_TTL_SECONDS

    async def _fetch_jwks(self, force: bool = False) -> None:
        if not force and not self._is_cache_stale():
            return
        async with httpx.AsyncClient() as client:
            response = await client.get(settings.azure_ad_jwks_url)
            response.raise_for_status()
            keys = response.json().get("keys", [])
            self._jwks = {key["kid"]: key for key in keys}
            self._jwks_fetched_at = time.monotonic()
            logger.info("jwks_fetched", key_count=len(self._jwks))

    async def validate_token(
        self,
        token: str,
        client_ip: str = "unknown",
        user_agent: str = "unknown",
        correlation_id: str = "",
    ) -> TokenPayload:
        try:
            await self._fetch_jwks()

            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid or kid not in self._jwks:
                await self._fetch_jwks(force=True)
                if kid not in self._jwks:
                    logger.warning(
                        "auth_failure",
                        reason="signing_key_not_found",
                        client_ip=client_ip,
                        user_agent=user_agent,
                        correlation_id=correlation_id,
                    )
                    raise UnauthorizedError("Token signing key not found")

            jwk_data = self._jwks[kid]
            public_key = cast("RSAPublicKey", jwt.algorithms.RSAAlgorithm.from_jwk(jwk_data))
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=[
                    settings.azure_ad_client_id,
                    f"api://{settings.azure_ad_client_id}",
                ],
                issuer=[
                    settings.azure_ad_issuer,
                    settings.azure_ad_issuer_v1,
                ],
            )

            return TokenPayload(
                sub=payload["sub"],
                oid=payload.get("oid", payload["sub"]),
                tid=payload.get("tid", ""),
                preferred_username=payload.get("preferred_username"),
                name=payload.get("name"),
                roles=payload.get("roles", []),
            )
        except PyJWTError as e:
            logger.warning(
                "auth_failure",
                reason="token_validation_failed",
                error=str(e),
                client_ip=client_ip,
                user_agent=user_agent,
                correlation_id=correlation_id,
            )
            raise UnauthorizedError("Invalid or expired token") from e


entra_auth = EntraIDAuth()
