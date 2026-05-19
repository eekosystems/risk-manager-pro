import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.models.conversation import Conversation, FunctionType
from app.models.document import Document, DocumentStatus
from app.models.message import MessageRole
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.repositories.document import DocumentRepository
from app.schemas.chat import ChatRequest, ChatResponse, CitationSchema, MessageResponse
from app.schemas.settings import PromptsPayload
from app.services.openai_client import AzureOpenAIClient
from app.services.prompts import (
    GENERAL_PROMPT,
    PHL_PROMPT,
    RISK_REGISTER_PROMPT,
    SRA_PROMPT,
    SYSTEM_ANALYSIS_PROMPT,
)
from app.services.rag import RAGService, SearchResult
from app.services.risk import RiskService
from app.services.routing import classify_function
from app.services.rr_tools import RR_TOOLS, execute_tool_call
from app.services.settings import SettingsService
from app.services.sharepoint_crawler import SharePointCrawler

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
    FunctionType.RISK_REGISTER: RISK_REGISTER_PROMPT,
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
        FunctionType.RISK_REGISTER: prompts.risk_register_prompt,
    }
    return prompt_map[function_type]


_FILENAME_RE = re.compile(
    r"[^\s'\"<>(){},;]+\.(?:pdf|docx|doc|xlsx|xls|pptx|ppt|txt|csv)\b",
    re.IGNORECASE,
)


def _extract_referenced_filenames(query: str) -> list[str]:
    """Pull any document filenames the user typed into the query."""
    return _FILENAME_RE.findall(query)


# Tokens that should not drive filename matching even though they're long enough.
# We strip common chat verbs and filler so e.g. "tell me about the CSPP document"
# narrows to ["cspp"] rather than spuriously matching files named "Document …".
_QUERY_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "and", "but", "for", "you", "your", "our", "their", "this",
        "that", "these", "those", "with", "from", "into", "have", "has",
        "had", "are", "was", "were", "been", "being", "any", "all", "some",
        "what", "when", "where", "which", "who", "whom", "why", "how",
        "can", "could", "would", "should", "may", "might", "will", "shall",
        "did", "does", "doing", "tell", "show", "give", "ask", "see", "read",
        "find", "look", "looking", "about", "regarding", "concerning",
        "file", "files", "document", "documents", "doc", "docs", "pdf",
        "docx", "txt", "upload", "uploaded", "uploads", "uploading",
        "most", "recent", "latest", "just", "now", "today", "yesterday",
        "name", "names", "named", "called", "title", "titled",
        "please", "thanks", "thank", "hello", "hey", "yes", "yeah",
        "want", "need", "like", "know", "get", "got", "make", "made",
        "use", "used", "using", "say", "said", "telling",
        "between", "over", "under", "more", "less", "than", "then",
        "out", "off", "yet", "still", "very", "much", "many", "few",
    }
)

# Phrases that indicate the user is referencing a recent upload by pronoun
# ("the file I just uploaded", "that doc", "the most recent one"). When any of
# these match AND the query carries no explicit filename, the most-recently-
# uploaded doc gets used as a source filter so retrieval pulls its content.
_RECENT_UPLOAD_REF_RE = re.compile(
    r"\b("
    r"just\s+uploaded|"
    r"recently\s+uploaded|"
    r"most\s+recent|"
    r"the\s+(?:file|doc|document|pdf|upload|attachment)|"
    r"that\s+(?:file|doc|document|pdf|upload|attachment)|"
    r"this\s+(?:file|doc|document|pdf|upload|attachment)|"
    r"my\s+(?:file|doc|document|pdf|upload|attachment)|"
    r"latest\s+(?:file|doc|document|pdf|upload)"
    r")\b",
    re.IGNORECASE,
)

# Splits filenames (and the user's query) into comparable tokens. Treats common
# separators as boundaries so "CSPP_Seattle_Runway-2024.pdf" → cspp/seattle/runway/2024.
_TOKEN_SPLIT_RE = re.compile(r"[\W_]+", re.UNICODE)


def _normalize_token(token: str) -> str:
    """Light stemming so plurals match singular filename tokens (e.g. CSPPs → CSPP)."""
    if len(token) >= 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) >= 5 and token.endswith("es") and not token.endswith("ses"):
        return token[:-2]
    if len(token) >= 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-word chars, drop short/stopword tokens, light-stem."""
    raw = _TOKEN_SPLIT_RE.split(text.lower())
    return [
        _normalize_token(t)
        for t in raw
        if len(t) >= 3 and t not in _QUERY_STOPWORDS
    ]


def _filename_stem_tokens(filename: str) -> list[str]:
    """Tokenize a filename ignoring its extension."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return _tokenize(stem)


def _references_recent_upload(query: str) -> bool:
    """True when the query reads as a pronoun reference to an uploaded doc."""
    return bool(_RECENT_UPLOAD_REF_RE.search(query))


def _match_candidate_filenames(
    query: str, filenames: list[str], max_candidates: int = 12
) -> list[str]:
    """Return filenames whose tokens overlap with the user's query, ranked by overlap.

    Empty result means the user did not name any indexed file (the model will
    fall back to generic semantic search). A single result is a confident hit.
    Multiple results means the model needs to disambiguate with the user.
    """
    query_tokens = set(_tokenize(query))
    if not query_tokens or not filenames:
        return []

    scored: list[tuple[int, int, str]] = []  # (-overlap, -length_match, filename)
    for fname in filenames:
        fname_tokens = set(_filename_stem_tokens(fname))
        if not fname_tokens:
            continue
        overlap = len(query_tokens & fname_tokens)
        if overlap == 0:
            continue
        # Tie-break: prefer filenames whose token set is closer in size to the
        # overlap (i.e. a 2-token file matched by 2 tokens beats a 10-token
        # file matched by 2 tokens, which would be coincidental).
        scored.append((-overlap, len(fname_tokens), fname))

    scored.sort()
    return [f for _, _, f in scored[:max_candidates]]


def _format_doc_status(status: DocumentStatus) -> str:
    """Human-readable status label for the inventory block."""
    if status == DocumentStatus.INDEXED:
        return "indexed"
    if status == DocumentStatus.FAILED:
        return "indexing failed"
    return "still processing"


def _build_recent_uploads_block(
    docs: list[Document],
    session_upload_ids: set[uuid.UUID] | None = None,
) -> str | None:
    """Render the org's most recently uploaded files (most recent first).

    When `session_upload_ids` is provided, docs in that set are tagged as
    uploaded by the current user in the active session so the model can
    answer "the file I just uploaded" precisely.
    """
    if not docs:
        return None
    session_ids = session_upload_ids or set()
    lines: list[str] = []
    for doc in docs:
        tag = _format_doc_status(doc.status)
        if doc.id in session_ids:
            tag += "; uploaded by you in this session"
        lines.append(f"- {doc.filename} ({tag})")
    return (
        "Files most recently uploaded to this organization (most recent first; "
        "this list IS the authoritative answer for recency and inventory "
        "questions):\n" + "\n".join(lines)
    )


def _build_candidates_block(candidates: list[str], total_in_org: int) -> str | None:
    """Render the candidate documents matched against the user's query."""
    if not candidates:
        return None
    visible_limit = 8
    visible = candidates[:visible_limit]
    extra = max(0, len(candidates) - visible_limit)
    lines = [f"- {name}" for name in visible]
    if extra > 0:
        lines.append(f"- …and {extra} more")
    header = (
        "Indexed documents in this organization whose filenames match the "
        f"user's request ({len(candidates)} of {total_in_org} total):"
    )
    return header + "\n" + "\n".join(lines)


_FILE_AWARENESS_INSTRUCTIONS = (
    "File awareness rules:\n"
    "- The lists above ARE the authoritative answer for what files exist in "
    "this organization and what the user has recently uploaded. Treat them "
    "as ground truth — do NOT hedge with phrases like \"based on the context "
    "provided\", \"limited to what's shown\", or \"I don't have access to "
    "your file repository\".\n"
    "- When the user asks the name of a file, which file they uploaded, "
    "which is most recent, or to list their files, answer with the bare "
    "filename(s) only (e.g. \"Seattle CSPP 2024.pdf\"). Do NOT add chunk "
    "numbers, \"[Source N]\" labels, section names, or any other RAG "
    "retrieval terminology in prose. The UI renders source citation chips "
    "separately — your job is to name the file plainly. This overrides the "
    "general \"reference sources by number\" rule for file-identity "
    "questions.\n"
    "- \"Recently uploaded\" means the list under \"Files this user "
    "recently uploaded\" above, ordered most recent first. Use that order — "
    "do not re-infer recency from the order of retrieved chunks.\n"
    "- If the user's request appears to target a single specific document "
    "and the candidate list above contains more than one match, ask the user "
    "which one they mean before answering. List the candidate filenames so "
    "the user can pick. Do not guess.\n"
    "- If the user's request is plural or comparative (e.g. \"compare\", "
    "\"all of them\", \"our CSPPs\"), do not ask — synthesize across the "
    "matching documents.\n"
    "- If the candidate list is empty but the user names a file, say you "
    "could not find a matching document in their library."
)


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
        source_label = f"[Source {i}: {r.source}"
        if r.section:
            source_label += f" — {r.section}"
        source_label += "]"
        sections.append(f"{source_label}\n{r.content}")

    return "\n\n---\n\n".join(sections)


# The frontend picks up suggestion chips by matching `<followups>...</followups>`
# at the very end of the assistant content. The model is instructed to emit this
# block on every reply, but on long outputs (especially PHL, which also emits an
# `<rr_payload>` block) it occasionally truncates or omits it. The helpers below
# detect that case and inject a mode-appropriate default so the user always sees
# next-step chips.
_FOLLOWUPS_END_RE = re.compile(
    r"<followups>[\s\S]*?</followups>\s*$",
    re.IGNORECASE,
)
_FOLLOWUPS_OPEN_RE = re.compile(r"<followups>", re.IGNORECASE)
_FOLLOWUPS_CLOSE_RE = re.compile(r"</followups>", re.IGNORECASE)

_DEFAULT_FOLLOWUPS_BY_FUNCTION: dict[FunctionType, str] = {
    FunctionType.GENERAL: (
        "forward | sra | Run an SRA on a hazard | Run a Safety Risk Assessment on a hazard from this discussion.\n"
        "confirm | general | Confirm Output Accuracy | Confirm the output above is accurate before we proceed.\n"
        "clarify | general | Cite Relevant Regulatory Guidance | Cite the relevant FAA, ICAO, or EASA guidance for this topic.\n"
        "explore | view_risk_register | View Risk Register | -"
    ),
    FunctionType.SYSTEM_ANALYSIS: (
        "forward | phl | Generate PHL From This System | Generate a Preliminary Hazard List from this system description.\n"
        "confirm | general | Confirm System Analysis Accuracy | Confirm the system analysis above is accurate before we proceed.\n"
        "clarify | system | Examine Other System Interfaces | What other systems or interfaces should we consider in this analysis?\n"
        "explore | sra | Run SRA On A Hazard | Run a Safety Risk Assessment on a hazard from this system."
    ),
    FunctionType.PHL: (
        "forward | sra | Determine Full Risk For Top Hazard | Determine the full risk score for the highest-risk hazard from this PHL, including likelihood, severity, initial and residual risk.\n"
        "confirm | general | Confirm PHL Accuracy | Confirm the hazards identified above are accurate and complete before we proceed.\n"
        "revise | phl | Identify Additional Missed Hazards | Identify additional hazards we may have missed in this PHL.\n"
        "explore | risk_register | Add Hazards To Risk Register | Add the hazards from this PHL to the Risk Register."
    ),
    FunctionType.SRA: (
        "forward | risk_register | Add Assessed Hazard To Register | Add this assessed hazard to the Risk Register.\n"
        "confirm | general | Confirm Risk Scoring Accuracy | Confirm the risk scoring above is correct before we proceed.\n"
        "revise | sra | Re-Run With Different Controls | Re-run this SRA evaluating different proposed controls.\n"
        "clarify | general | Explain The Residual Risk Score | Explain how the residual risk score was derived."
    ),
    FunctionType.RISK_REGISTER: (
        "forward | view_risk_register | View Risk Register | -\n"
        "confirm | general | Confirm Risk Register Entry | Confirm the Risk Register entry above is accurate before we proceed.\n"
        "revise | risk_register | Add Another Hazard To Register | I'd like to add another hazard to the Risk Register.\n"
        "explore | sra | Run SRA On Captured Hazard | Run a Safety Risk Assessment on the hazard I just captured."
    ),
}


def _build_default_followups_block(function_type: FunctionType) -> str:
    body = _DEFAULT_FOLLOWUPS_BY_FUNCTION.get(
        function_type, _DEFAULT_FOLLOWUPS_BY_FUNCTION[FunctionType.GENERAL]
    )
    return f"<followups>\n{body}\n</followups>"


def _ensure_followups_block(content: str, function_type: FunctionType) -> tuple[str, str | None]:
    """Guarantee the assistant content ends with a parseable <followups> block.

    Returns (final_content, appended_text). `appended_text` is None when the
    model already emitted a valid block; otherwise it is the suffix that was
    appended (so streaming callers can replay it as deltas).
    """
    if _FOLLOWUPS_END_RE.search(content):
        return content, None

    cleaned = content
    open_count = len(_FOLLOWUPS_OPEN_RE.findall(cleaned))
    close_count = len(_FOLLOWUPS_CLOSE_RE.findall(cleaned))
    if open_count > close_count:
        last_open = list(_FOLLOWUPS_OPEN_RE.finditer(cleaned))[-1]
        cleaned = cleaned[: last_open.start()].rstrip()

    block = _build_default_followups_block(function_type)
    suffix = ("\n\n" if cleaned else "") + block
    return cleaned + suffix, suffix


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
        self._doc_repo = DocumentRepository(db)

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
        implicit_source_filter: list[str] | None = None,
    ) -> tuple[list[SearchResult], str]:
        """Run RAG search and return filtered results with a formatted context block.

        Source-filter precedence (first non-empty wins for the targeted search):
          1. Explicit filenames typed by the user (`Foo.pdf`).
          2. `implicit_source_filter` — resolved upstream from pronoun references
             ("the file I just uploaded") or single-candidate filename matches.
        If neither yields hits, falls back to an unfiltered hybrid search so the
        model still has something to work with.
        """
        search_results: list[SearchResult] = []
        referenced_filenames = _extract_referenced_filenames(query)
        targeted_filter = referenced_filenames or (implicit_source_filter or [])
        try:
            if targeted_filter:
                search_results = await self._rag.hybrid_search(
                    query,
                    organization_id=organization_id,
                    top_k=max(top_k, 20),
                    source_filter=targeted_filter,
                )
            if not search_results:
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

    async def _resolve_document_context(
        self,
        request: ChatRequest,
        organization_id: uuid.UUID,
    ) -> tuple[list[Document], set[uuid.UUID], list[str], int, list[str]]:
        """Gather the document signals the model needs to be file-aware.

        Returns:
            recent_docs: the org's most recently uploaded docs (any status,
                most recent first). Always populated when the org has any
                documents — independent of frontend localStorage state — so
                "what's the most recent file" always has an authoritative
                source.
            session_upload_ids: IDs the frontend reported as uploaded in the
                current session. Used to tag entries in `recent_docs` as
                "uploaded by you" and to drive pronoun-based RAG filtering.
            candidates: indexed filenames in the org whose tokens overlap with
                the user's query (ranked, capped). Used both for the awareness
                block and — when exactly one match — as an implicit RAG filter.
            total_indexed: how many indexed docs exist in the org.
            implicit_filter: filenames to pass to RAG as a source filter when
                the user did not type an explicit filename.
        """
        try:
            recent_docs = await self._doc_repo.list_recent_documents(
                organization_id, limit=10
            )
        except Exception:
            logger.error(
                "recent_documents_fetch_failed",
                organization_id=str(organization_id),
                exc_info=True,
            )
            recent_docs = []

        session_upload_ids: set[uuid.UUID] = set(request.recent_upload_ids or [])

        try:
            all_filenames = await self._doc_repo.list_indexed_filenames(
                organization_id
            )
        except Exception:
            logger.error(
                "indexed_filenames_fetch_failed",
                organization_id=str(organization_id),
                exc_info=True,
            )
            all_filenames = []

        candidates = _match_candidate_filenames(request.message, all_filenames)

        implicit_filter: list[str] = []
        if not _extract_referenced_filenames(request.message):
            if _references_recent_upload(request.message):
                # Prefer a session upload by THIS user; otherwise fall back to
                # the org's most-recently-indexed doc.
                session_indexed = [
                    d.filename
                    for d in recent_docs
                    if d.id in session_upload_ids
                    and d.status == DocumentStatus.INDEXED
                ]
                if session_indexed:
                    implicit_filter = session_indexed[:1]
                else:
                    org_indexed = [
                        d.filename
                        for d in recent_docs
                        if d.status == DocumentStatus.INDEXED
                    ]
                    if org_indexed:
                        implicit_filter = org_indexed[:1]
            elif len(candidates) == 1:
                implicit_filter = candidates

        return recent_docs, session_upload_ids, candidates, len(all_filenames), implicit_filter

    async def _prepare_messages(
        self,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        function_type: FunctionType,
        prompts_config: PromptsPayload | None,
        context_block: str,
        recent_docs: list[Document] | None = None,
        session_upload_ids: set[uuid.UUID] | None = None,
        candidates: list[str] | None = None,
        total_indexed: int = 0,
    ) -> list[dict[str, str]]:
        """Build the full message list for the model: system prompt, history, and RAG context."""
        system_prompt = _resolve_prompt(function_type, prompts_config)

        reasoning_instructions = (
            "When answering, follow this structure using markdown headers (not numbered lists):\n\n"
            "### Answer\n"
            "Provide your analysis or recommendation. Reference sources by number "
            "(e.g. [Source 1]) inline where relevant.\n\n"
            "### Reasoning\n"
            "Briefly explain your logic — which sources you relied on, "
            "why they are relevant to the question, and how you arrived at your conclusion. "
            "Quote key passages.\n\n"
            "Formatting rules:\n"
            "- Always put the Answer section first, then Reasoning.\n"
            "- Use markdown headers (###) for sections, NEVER numbered top-level sections.\n"
            "- For risk levels, use bold colored labels: **High**, **Medium**, **Low**. "
            "Do NOT put colors in parentheses like '(Red)' or '(Yellow)' — just use the label.\n"
            "- Do NOT display numerical scores, percentages, or match tier labels "
            "(High/Moderate/Low) next to sources anywhere in your response.\n"
            "- If a source has low relevance or doesn't directly support your answer, "
            "say so rather than forcing a connection.\n"
            "- Do NOT display performance-indicator classifications (Leading, "
            "Lagging, Predictive) as labels, tags, sections, callouts, or table "
            "columns anywhere in your response. Use the Leading/Lagging/Predictive "
            "framework internally to strengthen your analysis and reasoning, but do "
            "not surface the classification itself to the user. This overrides any "
            "instruction in the system prompt to include performance-indicator "
            "classification, mapping, or pillar classification in the body of the "
            "output.\n"
            "- Do NOT include a 'Sources Used' section, a source list, or a "
            "Confidentiality Warning in your output. The client UI renders source "
            "citations as clickable chips and displays the confidentiality warning "
            "automatically in its own footer — duplicating them in the text would "
            "clutter the output. This overrides any instruction in the system "
            "prompt to include those sections in the body of the response."
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

        awareness_sections: list[str] = []
        recent_block = _build_recent_uploads_block(
            recent_docs or [], session_upload_ids
        )
        if recent_block:
            awareness_sections.append(recent_block)
        candidates_block = _build_candidates_block(candidates or [], total_indexed)
        if candidates_block:
            awareness_sections.append(candidates_block)
        if awareness_sections:
            awareness_sections.append(_FILE_AWARENESS_INSTRUCTIONS)
            messages.append(
                {"role": "system", "content": "\n\n".join(awareness_sections)}
            )

        for msg in history:
            messages.append({"role": msg.role.value, "content": msg.content})

        return messages

    async def _run_tool_loop(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        max_iterations: int = 5,
    ) -> str:
        """Run a tool-calling loop for Risk Register chat mode.

        The model may call `save_risk_register_record` one or more times. After
        each tool call we execute it server-side and append the result as a
        role="tool" message, then re-invoke the model. Loop terminates when
        the model stops emitting tool calls (it produces a final text reply),
        or after `max_iterations` to avoid runaway loops.
        """
        risk_service = RiskService(self._db)
        sharepoint = SharePointCrawler()
        loop_messages: list[dict[str, Any]] = list(messages)

        try:
            for iteration in range(max_iterations):
                response = await self._openai.chat_completion_with_tools(
                    loop_messages,
                    tools=RR_TOOLS,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                tool_calls = response["tool_calls"]
                if not tool_calls:
                    content: str = response["content"]
                    return content

                loop_messages.append(
                    {
                        "role": "assistant",
                        "content": response["content"] or "",
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                for tc in tool_calls:
                    result = await execute_tool_call(
                        tool_call=tc,
                        risk_service=risk_service,
                        sharepoint=sharepoint,
                        user_id=user_id,
                        organization_id=organization_id,
                        conversation_id=conversation_id,
                    )
                    loop_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        }
                    )

                logger.info(
                    "rr_tool_loop_iteration",
                    iteration=iteration + 1,
                    tool_call_count=len(tool_calls),
                    conversation_id=str(conversation_id),
                )
        finally:
            await sharepoint.close()

        logger.warning(
            "rr_tool_loop_exhausted",
            conversation_id=str(conversation_id),
            max_iterations=max_iterations,
        )
        return (
            "I saved what I could but ran into an issue completing the final "
            "confirmation. Please check the Risk Register to verify the record was "
            "created, and try again if anything is missing."
        )

    async def _route_function_type(
        self,
        request: ChatRequest,
        conversation: Conversation,
    ) -> FunctionType:
        """Pick the prompt for this turn. Falls back to request.function_type.

        Guards (in order):
          1. routing_locked → user clicked a follow-up chip; trust the mode
             they confirmed and skip classification entirely.
          2. Killswitch off → keep request.function_type.
          3. Tool flow in progress on the conversation (RISK_REGISTER) →
             never reroute; the wizard's multi-turn tool loop must not be
             interrupted by a mid-flow user reply (e.g. "JFK") being
             misclassified as something else.
          4. Otherwise classify every turn so the UI can live-switch.
        """
        if request.routing_locked:
            return request.function_type
        if not app_settings.chat_smart_routing:
            return request.function_type
        if conversation.function_type == FunctionType.RISK_REGISTER:
            return FunctionType.RISK_REGISTER
        return await classify_function(
            request.message, self._openai, fallback=request.function_type
        )

    async def _pin_risk_register_if_routed(
        self,
        conversation: Conversation,
        routed_function: FunctionType,
        organization_id: uuid.UUID,
    ) -> None:
        """Persist a flip into Risk Register on the conversation row.

        When a chip click routes a non-Risk-Register conversation into
        Risk Register, the first turn rides on `routing_locked=true` and
        works fine. But the user's follow-up replies ("KSFO", "Severity 3")
        come back with `routing_locked=false`, and the smart-routing
        classifier won't recognize a one-word reply as Risk Register —
        so the model loses RR_TOOLS and `save_risk_register_record` is
        never called. Pinning the conversation's `function_type` here
        means guard 3 in `_route_function_type` keeps every subsequent
        turn in Risk Register until the chat ends.
        """
        if routed_function != FunctionType.RISK_REGISTER:
            return
        if conversation.function_type == FunctionType.RISK_REGISTER:
            return
        await self._repo.set_function_type(
            conversation_id=conversation.id,
            organization_id=organization_id,
            function_type=FunctionType.RISK_REGISTER,
        )

    async def process_message(
        self, request: ChatRequest, user: User, organization_id: uuid.UUID
    ) -> ChatResponse:
        conversation = await self._resolve_conversation(request, user, organization_id)
        routed_function = await self._route_function_type(request, conversation)
        await self._pin_risk_register_if_routed(conversation, routed_function, organization_id)

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

        (
            recent_docs,
            session_upload_ids,
            candidates,
            total_indexed,
            implicit_filter,
        ) = await self._resolve_document_context(request, organization_id)

        search_results, context_block = await self._build_rag_context(
            query=request.message,
            organization_id=organization_id,
            conversation_id=conversation.id,
            top_k=rag_config.top_k,
            score_threshold=rag_config.score_threshold,
            implicit_source_filter=implicit_filter,
        )

        messages = await self._prepare_messages(
            conversation_id=conversation.id,
            organization_id=organization_id,
            function_type=routed_function,
            prompts_config=prompts_config,
            context_block=context_block,
            recent_docs=recent_docs,
            session_upload_ids=session_upload_ids,
            candidates=candidates,
            total_indexed=total_indexed,
        )

        if routed_function == FunctionType.RISK_REGISTER:
            assistant_content = await self._run_tool_loop(
                messages=messages,
                temperature=model_config.temperature,
                max_tokens=model_config.max_output_tokens,
                conversation_id=conversation.id,
                user_id=user.id,
                organization_id=organization_id,
            )
        else:
            assistant_content = await self._openai.chat_completion(
                messages,
                temperature=model_config.temperature,
                max_tokens=model_config.max_output_tokens,
            )

        assistant_content, appended_followups = _ensure_followups_block(
            assistant_content, routed_function
        )
        if appended_followups is not None:
            logger.info(
                "followups_block_injected",
                conversation_id=str(conversation.id),
                function_type=routed_function.value,
                streaming=False,
            )

        citations = _extract_citations(search_results) if search_results else None

        try:
            assistant_msg = await self._repo.add_message(
                conversation_id=conversation.id,
                organization_id=organization_id,
                role=MessageRole.ASSISTANT,
                content=assistant_content,
                citations=[c.model_dump() for c in citations] if citations else None,
            )
        except Exception:
            logger.error(
                "assistant_message_save_failed",
                conversation_id=str(conversation.id),
                user_id=str(user.id),
                content_length=len(assistant_content),
                citations_count=len(citations) if citations else 0,
                exc_info=True,
            )
            raise

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
            routed_function_type=routed_function,
        )

    async def process_message_stream(
        self, request: ChatRequest, user: User, organization_id: uuid.UUID
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream assistant tokens then persist the completed message.

        Yields event dicts: {"event": "metadata"|"delta"|"done"|"error", ...}.
        """
        conversation = await self._resolve_conversation(request, user, organization_id)
        routed_function = await self._route_function_type(request, conversation)
        await self._pin_risk_register_if_routed(conversation, routed_function, organization_id)

        await self._repo.add_message(
            conversation_id=conversation.id,
            organization_id=organization_id,
            role=MessageRole.USER,
            content=request.message,
        )

        rag_config = await self._settings.get_effective_rag_config(organization_id)
        model_config = await self._settings.get_effective_model_config(organization_id)
        try:
            prompts_config = await self._settings.get_effective_prompts(organization_id)
        except (ValueError, KeyError):
            prompts_config = None

        (
            recent_docs,
            session_upload_ids,
            candidates,
            total_indexed,
            implicit_filter,
        ) = await self._resolve_document_context(request, organization_id)

        search_results, context_block = await self._build_rag_context(
            query=request.message,
            organization_id=organization_id,
            conversation_id=conversation.id,
            top_k=rag_config.top_k,
            score_threshold=rag_config.score_threshold,
            implicit_source_filter=implicit_filter,
        )

        messages = await self._prepare_messages(
            conversation_id=conversation.id,
            organization_id=organization_id,
            function_type=routed_function,
            prompts_config=prompts_config,
            context_block=context_block,
            recent_docs=recent_docs,
            session_upload_ids=session_upload_ids,
            candidates=candidates,
            total_indexed=total_indexed,
        )

        yield {
            "event": "metadata",
            "conversation_id": str(conversation.id),
            "title": conversation.title,
            "routed_function_type": routed_function.value,
        }

        buffered: list[str] = []
        try:
            async for delta in self._openai.chat_completion_stream(
                messages,
                temperature=model_config.temperature,
                max_tokens=model_config.max_output_tokens,
            ):
                buffered.append(delta)
                yield {"event": "delta", "content": delta}
        except Exception as exc:
            logger.error(
                "chat_stream_failed",
                conversation_id=str(conversation.id),
                user_id=str(user.id),
                exc_info=True,
            )
            yield {"event": "error", "message": str(exc)}
            return

        assistant_content = "".join(buffered)
        assistant_content, appended_followups = _ensure_followups_block(
            assistant_content, routed_function
        )
        if appended_followups is not None:
            logger.info(
                "followups_block_injected",
                conversation_id=str(conversation.id),
                function_type=routed_function.value,
                streaming=True,
            )
            yield {"event": "delta", "content": appended_followups}

        citations = _extract_citations(search_results) if search_results else None
        assistant_msg = await self._repo.add_message(
            conversation_id=conversation.id,
            organization_id=organization_id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            citations=[c.model_dump() for c in citations] if citations else None,
        )

        yield {
            "event": "done",
            "message_id": str(assistant_msg.id),
            "citations": [c.model_dump(mode="json") for c in citations] if citations else None,
        }

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
