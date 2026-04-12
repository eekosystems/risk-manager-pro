import structlog
from azure.communication.email.aio import EmailClient
from azure.core.exceptions import AzureError
from azure.identity.aio import DefaultAzureCredential

from app.core.config import settings

logger = structlog.get_logger(__name__)


class EmailService:
    """Azure Communication Services email sender using managed identity."""

    def __init__(self) -> None:
        self._client: EmailClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> EmailClient:
        if self._client is None:
            if not settings.acs_endpoint:
                raise RuntimeError("ACS_ENDPOINT is required to send email in this environment")
            self._credential = DefaultAzureCredential()
            self._client = EmailClient(settings.acs_endpoint, self._credential)
        return self._client

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text_fallback: str,
        reply_to: str | None = None,
    ) -> bool:
        if not settings.acs_sender_address:
            logger.warning("email_send_skipped_no_sender", recipient=to)
            return False

        message: dict[str, object] = {
            "senderAddress": settings.acs_sender_address,
            "recipients": {"to": [{"address": to}]},
            "content": {
                "subject": subject,
                "plainText": text_fallback,
                "html": html,
            },
        }
        effective_reply_to = reply_to or settings.acs_reply_to_address
        if effective_reply_to:
            message["replyTo"] = [{"address": effective_reply_to}]

        try:
            client = await self._get_client()
            poller = await client.begin_send(message)
            result = await poller.result()
            status = result.get("status") if isinstance(result, dict) else None
            logger.info(
                "email_sent",
                recipient=to,
                subject=subject,
                status=status,
            )
            return True
        except AzureError as exc:
            logger.error(
                "email_send_failed",
                recipient=to,
                subject=subject,
                error=str(exc),
            )
            return False

    async def send_many(
        self,
        *,
        recipients: list[str],
        subject: str,
        html: str,
        text_fallback: str,
    ) -> dict[str, bool]:
        outcomes: dict[str, bool] = {}
        for recipient in recipients:
            outcomes[recipient] = await self.send(
                to=recipient,
                subject=subject,
                html=html,
                text_fallback=text_fallback,
            )
        return outcomes

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential is not None:
            await self._credential.close()


_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
