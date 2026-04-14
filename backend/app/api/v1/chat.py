import json
import uuid
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    get_openai_client,
    get_rag_service,
    require_analyst_or_above,
    require_any_member,
)
from app.core.exceptions import AppError, NotFoundError
from app.core.rate_limit import limiter
from app.models.notification import NotificationType
from app.models.organization import Organization
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListItem,
    EmailChatMessageRequest,
)
from app.schemas.common import DataResponse, MetaResponse
from app.services.audit import AuditLogger
from app.services.chat import ChatService
from app.services.email import get_email_service
from app.services.notification import NotificationDispatcher
from app.services.openai_client import AzureOpenAIClient
from app.services.rag import RAGService

logger = structlog.get_logger(__name__)

_notification_dispatcher = NotificationDispatcher()

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_chat_service(
    db: AsyncSession = Depends(get_db),
    openai_client: AzureOpenAIClient = Depends(get_openai_client),
    rag_service: RAGService = Depends(get_rag_service),
) -> ChatService:
    return ChatService(db=db, openai_client=openai_client, rag_service=rag_service)


@router.post("", response_model=DataResponse[ChatResponse], status_code=201)
@limiter.limit(settings.rate_limit_ai)
async def send_message(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: ChatService = Depends(_get_chat_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> DataResponse[ChatResponse]:
    result = await service.process_message(payload, current_user, organization.id)
    await audit.log(
        action="chat.message_sent",
        user=current_user,
        resource_type="conversation",
        resource_id=str(result.conversation_id),
        organization_id=organization.id,
    )
    _notification_dispatcher.dispatch(
        organization_id=organization.id,
        triggered_by=current_user,
        notification_type=NotificationType.CHAT_RESPONSE,
        title=f"AI response in: {result.title or 'conversation'}",
        body=result.message.content[:500],
        resource_type="conversation",
        resource_id=str(result.conversation_id),
    )
    try:
        response: DataResponse[ChatResponse] = DataResponse(
            data=result,
            meta=MetaResponse(request_id=str(result.conversation_id)),
        )
    except Exception:
        logger.error(
            "chat_response_serialization_failed",
            conversation_id=str(result.conversation_id),
            message_id=str(result.message.id),
            citations_count=len(result.message.citations) if result.message.citations else 0,
            exc_info=True,
        )
        raise
    return response


@router.post("/stream")
@limiter.limit(settings.rate_limit_ai)
async def send_message_stream(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: ChatService = Depends(_get_chat_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> StreamingResponse:
    async def _sse() -> AsyncIterator[str]:
        conversation_id: str | None = None
        try:
            async for event in service.process_message_stream(
                payload, current_user, organization.id
            ):
                if event.get("event") == "metadata":
                    conversation_id = event.get("conversation_id")
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            if conversation_id:
                await audit.log(
                    action="chat.message_streamed",
                    user=current_user,
                    resource_type="conversation",
                    resource_id=conversation_id,
                    organization_id=organization.id,
                )

    return StreamingResponse(
        _sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/messages/email", status_code=202)
@limiter.limit(settings.rate_limit_default)
async def email_chat_message(
    request: Request,
    payload: EmailChatMessageRequest,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    audit: AuditLogger = Depends(get_audit_logger),
) -> dict[str, str]:
    email_service = get_email_service()
    html = _build_chat_email_html(payload.content)
    sent = await email_service.send(
        to=payload.to,
        subject=payload.subject,
        html=html,
        text_fallback=payload.content,
    )
    outcome = "success" if sent else "failure"
    await audit.log(
        action="chat.response.emailed",
        user=current_user,
        resource_type="chat_message",
        resource_id=None,
        organization_id=organization.id,
        outcome=outcome,
        metadata={"recipient": payload.to, "subject": payload.subject},
    )
    if not sent:
        raise AppError(
            code="EMAIL_SEND_FAILED",
            message="Email could not be delivered. Contact your administrator.",
            status_code=502,
        )
    return {"status": "sent"}


def _build_chat_email_html(content: str) -> str:
    import html as html_lib

    escaped = html_lib.escape(content).replace("\n", "<br>")
    return (
        '<!doctype html><html><body style="font-family:Segoe UI,Arial,sans-serif;'
        'color:#1f2937;line-height:1.5;">'
        '<h2 style="color:#1e3a8a;margin-bottom:8px;">Risk Manager Pro — AI response</h2>'
        f'<div style="white-space:normal;">{escaped}</div>'
        '<hr style="margin-top:24px;border:none;border-top:1px solid #e5e7eb;">'
        '<p style="font-size:12px;color:#6b7280;">Sent from Risk Manager Pro.</p>'
        "</body></html>"
    )


@router.get("/conversations", response_model=DataResponse[list[ConversationListItem]])
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: ChatService = Depends(_get_chat_service),
) -> DataResponse[list[ConversationListItem]]:
    conversations = await service.list_conversations(
        user_id=current_user.id,
        organization_id=organization.id,
        skip=skip,
        limit=limit,
    )
    items = [ConversationListItem.model_validate(c) for c in conversations]
    return DataResponse(data=items, meta=MetaResponse(request_id=""))


@router.get("/conversations/{conversation_id}", response_model=DataResponse[ConversationDetail])
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    service: ChatService = Depends(_get_chat_service),
) -> DataResponse[ConversationDetail]:
    conversation = await service.get_conversation(
        conversation_id, organization.id, user_id=current_user.id
    )
    if not conversation:
        raise NotFoundError("Conversation", str(conversation_id))
    detail = ConversationDetail.model_validate(conversation)
    return DataResponse(data=detail, meta=MetaResponse(request_id=str(conversation_id)))


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(require_analyst_or_above),
    organization: Organization = Depends(get_current_organization),
    service: ChatService = Depends(_get_chat_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> None:
    deleted = await service.delete_conversation(
        conversation_id, organization.id, user_id=current_user.id
    )
    if not deleted:
        raise NotFoundError("Conversation", str(conversation_id))
    await audit.log(
        action="chat.conversation_deleted",
        user=current_user,
        resource_type="conversation",
        resource_id=str(conversation_id),
        organization_id=organization.id,
    )
