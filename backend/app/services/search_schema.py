"""Azure AI Search index schema. Run: python -m app.services.search_schema"""

import asyncio
import sys

import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from app.core.config import settings

logger = structlog.get_logger(__name__)


def build_index_schema(index_name: str | None = None) -> SearchIndex:
    """Build the Azure AI Search index schema (pure, no I/O)."""
    name = index_name or settings.azure_search_index_name

    fields = [
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SimpleField(
            name="document_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="tenant_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SearchableField(
            name="source",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SearchableField(
            name="section",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            analyzer_name="en.microsoft",
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="rmp-vector-profile",
        ),
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
        SimpleField(
            name="chunk_index",
            type=SearchFieldDataType.Int32,
            sortable=True,
        ),
        SimpleField(
            name="created_at",
            type=SearchFieldDataType.DateTimeOffset,
            sortable=True,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="rmp-hnsw-config",
                parameters=HnswParameters(
                    m=4,
                    ef_construction=400,
                    ef_search=500,
                    metric="cosine",
                ),
            ),
        ],
        profiles=[
            VectorSearchProfile(
                name="rmp-vector-profile",
                algorithm_configuration_name="rmp-hnsw-config",
            ),
        ],
    )

    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=vector_search,
    )


async def create_or_update_index(index_name: str | None = None) -> str:
    """Create or update the search index in Azure AI Search."""
    if not settings.azure_search_endpoint:
        raise RuntimeError(
            "AZURE_SEARCH_ENDPOINT is not configured. "
            "Set it in .env or environment variables."
        )

    index = build_index_schema(index_name)
    credential = DefaultAzureCredential()

    try:
        async with SearchIndexClient(
            endpoint=settings.azure_search_endpoint,
            credential=credential,
        ) as client:
            result = await client.create_or_update_index(index)
            logger.info(
                "search_index_created_or_updated",
                index_name=result.name,
                field_count=len(result.fields),
            )
            return result.name
    finally:
        await credential.close()


async def _main() -> None:
    """CLI entry point for creating the index."""
    try:
        name = await create_or_update_index()
        logger.info("search_index_ready", index_name=name)
    except RuntimeError as e:
        logger.error("search_index_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
