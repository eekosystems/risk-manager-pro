import uuid

import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient

from app.core.config import settings

logger = structlog.get_logger(__name__)


class SearchIndexer:
    def __init__(self) -> None:
        self._client: SearchClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> SearchClient:
        if self._client is None:
            if not settings.azure_search_endpoint:
                raise RuntimeError("Azure AI Search endpoint not configured")
            self._credential = DefaultAzureCredential()
            self._client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index_name,
                credential=self._credential,
            )
        return self._client

    async def index_chunks(
        self,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        source: str,
        chunks: list[str],
        embeddings: list[list[float]],
        source_type: str = "client",
    ) -> int:
        client = await self._get_client()

        documents = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            chunk_id = f"{document_id}_{i}"
            documents.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": str(document_id),
                    "tenant_id": str(organization_id),
                    "source": source,
                    "source_type": source_type,
                    "section": f"Chunk {i + 1}",
                    "content": chunk,
                    "content_vector": embedding,
                }
            )

        batch_size = settings.search_index_batch_size
        indexed = 0
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            result = await client.upload_documents(documents=batch)
            indexed += sum(1 for r in result if r.succeeded)

        logger.info(
            "chunks_indexed",
            document_id=str(document_id),
            total_chunks=len(chunks),
            indexed=indexed,
        )
        return indexed

    async def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Delete all indexed chunks for a document. Returns count of deleted chunks."""
        client = await self._get_client()
        search_results = await client.search(
            search_text="*",
            filter=f"document_id eq '{document_id}'",
            select=["chunk_id"],
        )
        to_delete: list[dict[str, str]] = []
        async for result in search_results:
            to_delete.append({"chunk_id": result["chunk_id"]})

        deleted = 0
        batch_size = settings.search_index_batch_size
        for start in range(0, len(to_delete), batch_size):
            batch = to_delete[start : start + batch_size]
            result = await client.delete_documents(documents=batch)
            deleted += sum(1 for r in result if r.succeeded)

        logger.info(
            "chunks_deleted", document_id=str(document_id), deleted=deleted
        )
        return deleted

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        if self._credential:
            await self._credential.close()
