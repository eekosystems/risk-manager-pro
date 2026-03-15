import uuid

import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from pydantic import BaseModel

from app.core.config import settings
from app.services.openai_client import AzureOpenAIClient

logger = structlog.get_logger(__name__)


class SearchResult(BaseModel):
    content: str
    source: str
    source_type: str = "client"
    section: str | None = None
    score: float
    chunk_id: str


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
        self, query: str, organization_id: uuid.UUID, top_k: int = 5
    ) -> list[SearchResult]:
        try:
            validated_id = uuid.UUID(str(organization_id))
        except ValueError as e:
            raise ValueError(f"Invalid organization_id for search filter: {e}") from e

        embedding = await self._openai.embed(query)
        client = await self._get_search_client()

        vector_query = VectorizedQuery(
            vector=embedding,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        sanitized_org_id = str(validated_id).replace("'", "''")
        tenant_filter = f"tenant_id eq '{sanitized_org_id}'"

        results: list[SearchResult] = []
        search_results = await client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=tenant_filter,
            top=top_k,
            select=["content", "source", "source_type", "section", "chunk_id"],
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

    async def close(self) -> None:
        if self._search_client:
            await self._search_client.close()
        if self._credential:
            await self._credential.close()
