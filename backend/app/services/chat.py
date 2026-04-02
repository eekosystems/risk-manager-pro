import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, FunctionType
from app.models.message import MessageRole
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.schemas.chat import ChatRequest, ChatResponse, CitationSchema, MessageResponse
from app.schemas.settings import PromptsPayload
from app.services.openai_client import AzureOpenAIClient
from app.services.prompts import GENERAL_PROMPT, PHL_PROMPT, SRA_PROMPT, SYSTEM_ANALYSIS_PROMPT
from app.services.rag import RAGService, SearchResult
from app.services.settings import SettingsService

logger = structlog.get_logger(__name__)

# Fallback prompts keyed by function type, used by _resolve_prompt() when
# no org-level PromptsPayload is available.  The canonical default values
# live in app.services.prompts; settings.py uses the same source via
# DEFAULT_PROMPTS (a PromptsPayload instance) for the settings API.
SYSTEM_PROMPTS: dict[FunctionType, str] = {
    FunctionType.PHL: PHL_PROMPT,
    FunctionType.SRA: SRA_PROMPT,
    FunctionType.SYSTEM_ANALYSIS: SYSTEM_ANALYSIS_PROMPT,
    FunctionType.GENERAL: GENERAL_PROMPT,
}


def _resolve_prompt(function_type: FunctionType, prompts: PromptsPayload | None) -> str:
    """Get the prompt for a function type from org settings, falling back to hardcoded defaults."""
    if prompts is None:
        return SYSTEM_PROMPTS[function_type]

    prompt_map: dict[FunctionType, str] = {
        FunctionType.PHL: prompts.phl_prompt,
        FunctionType.SRA: prompts.sra_prompt,
        FunctionType.SYSTEM_ANALYSIS: prompts.system_analysis_prompt,
        FunctionType.GENERAL: prompts.system_prompt,
    }
    return prompt_map[function_type]


def _filter_by_threshold(results: list[SearchResult], threshold: float) -> list[SearchResult]:
    """Remove results below the relevance score threshold."""
    if not results:
        return results
    filtered = [r for r in results if r.score >= threshold]
    # Always keep at least the top result so the AI has something to work with
    if not filtered and results:
        filtered = [results[0]]
    return filtered


def _compute_match_tier(rank: int, score: float, total: int) -> str:
    """Assign a human-readable match tier based on rank position and relative score.

    RRF fusion scores are inherently low (top results ~0.03), so tier assignment
    is based primarily on rank order rather than raw score magnitude.
    """
    if rank == 1:
        return "High"
    if rank == 2:
        return "High" if total <= 3 else "Moderate"
    if rank <= 3:
        return "Moderate"
    return "Low"


_SOURCE_TYPE_LABELS: dict[str, str] = {
    "client": "Client Document",
    "faa": "FAA Regulation",
    "icao": "ICAO Standard",
    "easa": "EASA Regulation",
    "nasa_asrs": "NASA ASRS Report",
    "internal": "Internal Document",
}


def _build_context_block(results: list[SearchResult]) -> str:
    if not results:
        return "No relevant documents found in the knowledge base."

    sections: list[str] = []
    for i, r in enumerate(results, 1):
        tier = _compute_match_tier(i, r.score, len(results))
        type_label = _SOURCE_TYPE_LABELS.get(r.source_type, "Document")
        source_label = f"[Source {i}: {r.source} ({type_label})"
        if r.section:
            source_label += f" — {r.section}"
        source_label += f" | Match: {tier}]"
        sections.append(f"{source_label}\n{r.content}")

    return "\n\n---\n\n".join(sections)


def _extract_citations(results: list[SearchResult]) -> list[CitationSchema]:
    total = len(results)
    return [
        CitationSchema(
            source=r.source,
            source_type=r.source_type,
            section=r.section,
            content=r.content,
            chunk_id=r.chunk_id,
            rank=i,
            match_tier=_compute_match_tier(i, r.score, total),
        )
        for i, r in enumerate(results, 1)
    ]


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        openai_client: AzureOpenAIClient,
        rag_service: RAGService,
        settings_service: SettingsService | None = None,
    ) -> None:
        self._db = db
        self._openai = openai_client
        self._rag = rag_service
        self._settings = settings_service or SettingsService(db)
        self._repo = ConversationRepository(db)

    async def _resolve_conversation(
        self,
        request: ChatRequest,
        user: User,
        organization_id: uuid.UUID,
    ) -> Conversation:
        """Find an existing conversation by ID or create a new one."""
        if request.conversation_id:
            conversation = await self._repo.get_by_id(request.conversation_id, organization_id)
            if conversation:
                return conversation

        return await self._repo.create(
            user_id=user.id,
            organization_id=organization_id,
            title=request.message[:100],
            function_type=request.function_type,
        )

    async def _build_rag_context(
        self,
        query: str,
        organization_id: uuid.UUID,
        conversation_id: uuid.UUID,
        top_k: int,
        score_threshold: float,
    ) -> tuple[list[SearchResult], str]:
        """Run RAG search and return filtered results with a formatted context block."""
        search_results: list[SearchResult] = []
        try:
            search_results = await self._rag.hybrid_search(
                query,
                organization_id=organization_id,
                top_k=top_k,
            )
        except Exception:  # Deliberately broad: RAG failure must not crash the chat flow
            logger.error(
                "rag_search_failed",
                conversation_id=str(conversation_id),
                exc_info=True,
            )

        search_results = _filter_by_threshold(search_results, score_threshold)
        context_block = _build_context_block(search_results)
        return search_results, context_block

    async def _prepare_messages(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        function_type: FunctionType,
        prompts_config: PromptsPayload | None,
        context_block: str,
    ) -> list[dict[str, str]]:
        """Build the full message list for the model: system prompt, history, and RAG context."""
        system_prompt = _resolve_prompt(function_type, prompts_config)

        reasoning_instructions = (
            "When answering, follow this structure:\n"
            "1. **Reasoning:** Briefly explain your logic — which sources you relied on, "
            "why they are relevant to the question, and how you arrived at your conclusion. "
            "Reference sources by number (e.g. [Source 1]) and quote key passages.\n"
            "2. **Answer:** Provide your analysis or recommendation.\n"
            "3. **Sources Used:** List each source you cited with its match level "
            "(High, Moderate, or Low — shown next to each source above).\n\n"
            "Do NOT display numerical scores or percentages for relevance. "
            "Use only the match tier labels (High, Moderate, Low). "
            "If a source has low relevance or doesn't directly support your answer, "
            "say so rather than forcing a connection."
        )

        history = await self._repo.get_messages(conversation_id, organization_id, limit=20)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "system",
                "content": (
                    f"{reasoning_instructions}\n\n"
                    f"Relevant context from safety documentation:\n\n{context_block}"
                ),
            },
        ]
        for msg in history:
            messages.append({"role": msg.role.value, "content": msg.content})

        return messages

    async def process_message(
        self, request: ChatRequest, user: User, organization_id: uuid.UUID
    ) -> ChatResponse:
        conversation = await self._resolve_conversation(request, user, organization_id)

        await self._repo.add_message(
            conversation_id=conversation.id,
            organization_id=organization_id,
            role=MessageRole.USER,
            content=request.message,
        )

        # Load org-level settings
        rag_config = await self._settings.get_effective_rag_config(organization_id)
        model_config = await self._settings.get_effective_model_config(organization_id)
        try:
            prompts_config = await self._settings.get_effective_prompts(organization_id)
        except (ValueError, KeyError):
            prompts_config = None

        search_results, context_block = await self._build_rag_context(
            query=request.message,
            organization_id=organization_id,
            conversation_id=conversation.id,
            top_k=rag_config.top_k,
            score_threshold=rag_config.score_threshold,
        )

        messages = await self._prepare_messages(
            conversation_id=conversation.id,
            organization_id=organization_id,
            function_type=request.function_type,
            prompts_config=prompts_config,
            context_block=context_block,
        )

        assistant_content = await self._openai.chat_completion(
            messages,
            temperature=model_config.temperature,
            max_tokens=model_config.max_output_tokens,
        )
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
                citations=assistant_msg.citations,
                created_at=assistant_msg.created_at,
            ),
            title=conversation.title,
        )

    async def get_conversation(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Conversation | None:
        return await self._repo.get_by_id(conversation_id, organization_id, user_id=user_id)

    async def list_conversations(
        self, user_id: uuid.UUID, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[Conversation]:
        return await self._repo.list_for_user(user_id, organization_id, skip, limit)

    async def delete_conversation(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        return await self._repo.archive(conversation_id, organization_id, user_id=user_id)
