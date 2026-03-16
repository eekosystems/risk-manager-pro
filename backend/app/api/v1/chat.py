import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import (
    get_audit_logger,
    get_current_organization,
    get_current_user,
    get_openai_client,
    get_rag_service,
)
from app.core.exceptions import NotFoundError
from app.core.rate_limit import limiter
from app.models.organization import Organization
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListItem,
)
from app.schemas.common import DataResponse, MetaResponse
from app.models.notification import NotificationType
from app.services.audit import AuditLogger
from app.services.chat import ChatService
from app.services.notification import NotificationDispatcher
from app.services.openai_client import AzureOpenAIClient
from app.services.rag import RAGService

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
    current_user: User = Depends(get_current_user),
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
    return DataResponse(
        data=result,
        meta=MetaResponse(request_id=str(result.conversation_id)),
    )


@router.get("/conversations", response_model=DataResponse[list[ConversationListItem]])
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
