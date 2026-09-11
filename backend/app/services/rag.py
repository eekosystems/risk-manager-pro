import uuid
from typing import Literal

import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from pydantic import BaseModel

from app.core.config import settings
from app.services.openai_client import AzureOpenAIClient

logger = structlog.get_logger(__name__)

# M-4: hard ceiling on retrieved chunks, enforced server-side regardless of the
# per-org rag_config.top_k. Bounds both the Azure OpenAI/Search cost per call and
# the prompt-injection surface a poisoned document corpus can present to the model.
_MAX_TOP_K = 20

# Ceiling for reading a targeted document whole (see `fetch_documents`). Distinct
# from _MAX_TOP_K on purpose: relevance search caps how much of the *corpus* a
# query can pull in, whereas this caps how large a document the user explicitly
# selected may be before the analysis falls back to relevance search. At the
# 500-token chunk size this is roughly 60K tokens — a full CSPP narrative, well
# inside the model's input window, and still fenced as untrusted data.
MAX_DOCUMENT_CHUNKS = 120

_SELECT_FIELDS = ["content", "source", "source_type", "section", "chunk_id"]


class SearchResult(BaseModel):
    content: str
    source: str
    source_type: str = "client"
    section: str | None = None
    score: float
    chunk_id: str
    # How this chunk reached the prompt: ranked by a relevance query, or read as
    # part of a whole document the user targeted. Decides how it is cited.
    retrieved_by: Literal["search", "document"] = "search"


def _chunk_order(chunk_id: str) -> int:
    """Reading-order position encoded in the indexer's `<document_id>_<n>` ids.

    Documents indexed before `chunk_index` was populated carry their order only
    here, so this is the ordering key for every document, old or new.
    """
    _, _, suffix = chunk_id.rpartition("_")
    return int(suffix) if suffix.isdigit() else 0


def _build_filter(organization_id: uuid.UUID, source_filter: list[str] | None) -> str:
    try:
        validated_id = uuid.UUID(str(organization_id))
    except ValueError as e:
        raise ValueError(f"Invalid organization_id for search filter: {e}") from e

    sanitized_org_id = str(validated_id).replace("'", "''")
    filter_parts = [f"tenant_id eq '{sanitized_org_id}'"]
    if source_filter:
        # M-2: defense in depth on top of the single-quote escape — reject
        # control characters and absurdly long values that can't be a real
        # source/filename, so a raw user string can't be smuggled in here.
        for name in source_filter:
            if len(name) > 256 or any(ord(c) < 32 for c in name):
                raise ValueError("source_filter contains an invalid source name")
        sources_clause = " or ".join(
            f"source eq '{name.replace(chr(39), chr(39) + chr(39))}'" for name in source_filter
        )
        filter_parts.append(f"({sources_clause})")
    return " and ".join(filter_parts)


class RAGService:
    def __init__(self, openai_client: AzureOpenAIClient) -> None:
        self._openai = openai_client
        self._credential: DefaultAzureCredential | None = None
        self._search_client: SearchClient | None = None

    async def _get_search_client(self) -> SearchClient:
        if self._search_client is None:
            if not settings.azure_search_endpoint:
                raise RuntimeError("Azure AI Search endpoint not configured")
            self._credential = DefaultAzureCredential()
            self._search_client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index_name,
                credential=self._credential,
            )
        return self._search_client

    async def hybrid_search(
        self,
        query: str,
        organization_id: uuid.UUID,
        top_k: int = 5,
        source_filter: list[str] | None = None,
    ) -> list[SearchResult]:
        combined_filter = _build_filter(organization_id, source_filter)

        effective_top_k = max(1, min(top_k, _MAX_TOP_K))
        if effective_top_k != top_k:
            logger.warning("rag_top_k_capped", requested=top_k, effective=effective_top_k)
        top_k = effective_top_k

        embedding = await self._openai.embed(query)
        client = await self._get_search_client()

        vector_query = VectorizedQuery(
            vector=embedding,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        results: list[SearchResult] = []
        search_results = await client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=combined_filter,
            top=top_k,
            select=_SELECT_FIELDS,
        )
        async for result in search_results:
            results.append(
                SearchResult(
                    content=result["content"],
                    source=result.get("source", "Unknown"),
                    source_type=result.get("source_type", "client"),
                    section=result.get("section"),
                    score=result["@search.score"],
                    chunk_id=result.get("chunk_id", ""),
                )
            )

        logger.info("rag_search_complete", query_length=len(query), results_count=len(results))
        return results

    async def fetch_documents(
        self,
        organization_id: uuid.UUID,
        sources: list[str],
        max_chunks: int = MAX_DOCUMENT_CHUNKS,
    ) -> list[SearchResult] | None:
        """Every indexed chunk of the named documents, in reading order.

        Relevance search answers "which passages resemble the question"; a
        hazard analysis needs "what does this document say", including the
        phase-specific paragraph that resembles no question — a taxiway being
        decommissioned in one work area, a haul route closed in one phase.
        Returns None when the documents together exceed `max_chunks`, so the
        caller can fall back to relevance search rather than truncate silently.
        """
        if not sources:
            return []
        combined_filter = _build_filter(organization_id, sources)
        client = await self._get_search_client()

        results: list[SearchResult] = []
        search_results = await client.search(
            search_text="*",
            filter=combined_filter,
            top=max_chunks + 1,
            select=_SELECT_FIELDS,
        )
        async for result in search_results:
            results.append(
                SearchResult(
                    content=result["content"],
                    source=result.get("source", "Unknown"),
                    source_type=result.get("source_type", "client"),
                    section=result.get("section"),
                    score=1.0,
                    chunk_id=result.get("chunk_id", ""),
                    retrieved_by="document",
                )
            )

        if len(results) > max_chunks:
            logger.warning(
                "rag_document_exceeds_budget",
                sources=sources,
                chunks=len(results),
                max_chunks=max_chunks,
            )
            return None

        order = {name: i for i, name in enumerate(sources)}
        results.sort(key=lambda r: (order.get(r.source, len(order)), _chunk_order(r.chunk_id)))
        logger.info("rag_documents_fetched", sources=sources, chunks=len(results))
        return results

    async def close(self) -> None:
        if self._search_client:
            await self._search_client.close()
        if self._credential:
            await self._credential.close()
