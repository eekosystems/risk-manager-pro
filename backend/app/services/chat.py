import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, FunctionType
from app.models.message import MessageRole
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import ChatRequest, ChatResponse, CitationSchema, MessageResponse
from app.services.openai_client import AzureOpenAIClient
from app.services.rag import RAGService, SearchResult

logger = structlog.get_logger(__name__)

SYSTEM_PROMPTS: dict[FunctionType, str] = {
    FunctionType.PHL: (
        "You are an aviation safety AI assistant specializing in Preliminary Hazard Lists (PHL). "
        "Help users identify hazards, assess initial risk levels, and document potential dangers "
        "in aviation operations. Use the provided context from safety documentation to support "
        "your analysis. Always cite your sources. If the context does not support an answer, "
        "clearly state that. Follow FAA SMS guidelines for hazard identification."
    ),
    FunctionType.SRA: (
        "You are an aviation safety AI assistant specializing in Safety Risk Assessments (SRA). "
        "Help users evaluate risk severity and likelihood using standard 5x5 risk matrices per "
        "FAA SMS guidelines. Guide them through the SRM process: hazard identification, risk "
        "analysis, risk assessment, and risk control. Always cite your sources. Never fabricate "
        "safety data."
    ),
    FunctionType.SYSTEM_ANALYSIS: (
        "You are an aviation safety AI assistant specializing in System Safety Analysis. "
        "Help users analyze aviation systems for potential failure modes, common cause failures, "
        "and safety-critical interfaces. Reference ICAO Annex 19, FAR regulations, and industry "
        "best practices. Always cite your sources."
    ),
    FunctionType.GENERAL: (
        "You are an aviation safety AI assistant for Risk Manager Pro. Help users with "
        "operational risk management, safety documentation, regulatory compliance (FAA, ICAO, "
        "EASA), and safety management system (SMS) questions. Always cite your sources from "
        "the provided context. If the context does not contain relevant information, say so."
    ),
}


def _build_context_block(results: list[SearchResult]) -> str:
    if not results:
        return "No relevant documents found in the knowledge base."

    sections: list[str] = []
    for i, r in enumerate(results, 1):
        source_label = f"[Source {i}: {r.source}"
        if r.section:
            source_label += f" — {r.section}"
        source_label += "]"
        sections.append(f"{source_label}\n{r.content}")

    return "\n\n---\n\n".join(sections)


def _extract_citations(results: list[SearchResult]) -> list[CitationSchema]:
    return [
        CitationSchema(
            source=r.source,
            section=r.section,
            content=r.content[:200],
            score=r.score,
            chunk_id=r.chunk_id,
        )
        for r in results
    ]


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        openai_client: AzureOpenAIClient,
        rag_service: RAGService,
    ) -> None:
        self._db = db
        self._openai = openai_client
        self._rag = rag_service
        self._repo = ConversationRepository(db)

    async def process_message(
        self, request: ChatRequest, user: User, organization_id: uuid.UUID
    ) -> ChatResponse:
        if request.conversation_id:
            conversation = await self._repo.get_by_id(
                request.conversation_id, organization_id
            )
            if not conversation:
                conversation = await self._repo.create(
                    user_id=user.id,
                    organization_id=organization_id,
                    title=request.message[:100],
                    function_type=request.function_type,
                )
        else:
            conversation = await self._repo.create(
                user_id=user.id,
                organization_id=organization_id,
                title=request.message[:100],
                function_type=request.function_type,
            )

        await self._repo.add_message(
            conversation_id=conversation.id,
            organization_id=organization_id,
            role=MessageRole.USER,
            content=request.message,
        )

        search_results: list[SearchResult] = []
        try:
            search_results = await self._rag.hybrid_search(
                request.message, organization_id=organization_id, top_k=5
            )
        except Exception:
            logger.error(
                "rag_search_failed",
                conversation_id=str(conversation.id),
                exc_info=True,
            )

        context_block = _build_context_block(search_results)
        system_prompt = SYSTEM_PROMPTS[request.function_type]

        history = await self._repo.get_messages(conversation.id, organization_id, limit=20)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "system",
                "content": f"Relevant context from safety documentation:\n\n{context_block}",
            },
        ]
        for msg in history:
            messages.append({"role": msg.role.value, "content": msg.content})

        assistant_content = await self._openai.chat_completion(messages)
        citations = _extract_citations(search_results) if search_results else None

        assistant_msg = await self._repo.add_message(
            conversation_id=conversation.id,
            organization_id=organization_id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            citations=[c.model_dump() for c in citations] if citations else None,
        )

        logger.info(
            "chat_message_processed",
            conversation_id=str(conversation.id),
            user_id=str(user.id),
            citations_count=len(citations) if citations else 0,
        )

        return ChatResponse(
            conversation_id=conversation.id,
            message=MessageResponse(
                id=assistant_msg.id,
                role=assistant_msg.role.value,
                content=assistant_msg.content,
                citations=citations,
                created_at=assistant_msg.created_at,
            ),
            title=conversation.title,
        )

    async def get_conversation(
        self, conversation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Conversation | None:
        return await self._repo.get_by_id(conversation_id, organization_id)

    async def list_conversations(
        self, user_id: uuid.UUID, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[Conversation]:
        return await self._repo.list_for_user(user_id, organization_id, skip, limit)

    async def delete_conversation(
        self, conversation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> bool:
        return await self._repo.archive(conversation_id, organization_id)
