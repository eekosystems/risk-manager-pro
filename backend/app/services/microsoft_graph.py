"""Microsoft Graph API client for user lookup and B2B guest invitations."""

from __future__ import annotations

import httpx
import structlog
from azure.identity.aio import DefaultAzureCredential
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

logger = structlog.get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class GraphUser(BaseModel):
    object_id: str
    email: str
    display_name: str
    user_principal_name: str


class GraphInvitation(BaseModel):
    invited_user_id: str
    invite_redeem_url: str
    status: str


class MicrosoftGraphService:
    """Thin wrapper around Microsoft Graph REST API using DefaultAzureCredential."""

    def __init__(self) -> None:
        self._credential: DefaultAzureCredential | None = None
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._credential = DefaultAzureCredential()
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _get_token(self) -> str:
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        token = await self._credential.get_token(GRAPH_SCOPE)
        return token.token

    async def find_user_by_email(self, email: str) -> GraphUser | None:
        """Look up a user in the Entra ID directory by email or UPN."""
        try:
            client = await self._ensure_client()
            token = await self._get_token()
            response = await client.get(
                f"{GRAPH_BASE_URL}/users",
                params={
                    "$filter": f"mail eq '{email}' or userPrincipalName eq '{email}'",
                    "$select": "id,mail,displayName,userPrincipalName",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 403:
                logger.warning("graph_permission_denied", action="find_user")
                raise ExternalServiceError(
                    "Microsoft Graph", "Insufficient permissions to search directory"
                )

            if response.status_code >= 400:
                logger.error(
                    "graph_user_lookup_failed",
                    status=response.status_code,
                    body=response.text[:200],
                )
                raise ExternalServiceError(
                    "Microsoft Graph",
                    f"User lookup failed (HTTP {response.status_code})",
                )

            data = response.json()
            users = data.get("value", [])
            if not users:
                return None

            u = users[0]
            return GraphUser(
                object_id=u["id"],
                email=u.get("mail") or u.get("userPrincipalName", ""),
                display_name=u.get("displayName", "Unknown"),
                user_principal_name=u.get("userPrincipalName", ""),
            )

        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.error("graph_user_lookup_error", error=str(exc))
            raise ExternalServiceError(
                "Microsoft Graph", "Failed to connect to directory service"
            ) from exc

    async def send_b2b_invitation(
        self,
        email: str,
        redirect_url: str | None = None,
    ) -> GraphInvitation:
        """Send a B2B guest invitation via Microsoft Graph."""
        redirect = (
            redirect_url or settings.invitation_redirect_url or "https://myapps.microsoft.com"
        )
        try:
            client = await self._ensure_client()
            token = await self._get_token()
            response = await client.post(
                f"{GRAPH_BASE_URL}/invitations",
                json={
                    "invitedUserEmailAddress": email,
                    "inviteRedirectUrl": redirect,
                    "sendInvitationMessage": True,
                    "invitedUserMessageInfo": {
                        "customizedMessageBody": (
                            "You've been invited to Risk Manager Pro, "
                            "Faith Group's aviation safety management platform."
                        ),
                    },
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 403:
                logger.warning("graph_permission_denied", action="send_invitation")
                raise ExternalServiceError(
                    "Microsoft Graph", "Insufficient permissions to send invitations"
                )

            if response.status_code >= 400:
                logger.error(
                    "graph_invitation_failed",
                    status=response.status_code,
                    body=response.text[:200],
                )
                raise ExternalServiceError(
                    "Microsoft Graph",
                    f"Invitation failed (HTTP {response.status_code})",
                )

            data = response.json()
            return GraphInvitation(
                invited_user_id=data["invitedUser"]["id"],
                invite_redeem_url=data.get("inviteRedeemUrl", ""),
                status=data.get("status", "PendingAcceptance"),
            )

        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.error("graph_invitation_error", error=str(exc))
            raise ExternalServiceError("Microsoft Graph", "Failed to send invitation") from exc

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._credential:
            await self._credential.close()
            self._credential = None
