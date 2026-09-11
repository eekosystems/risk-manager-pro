"""Whole-document retrieval for analysis turns.

Relevance search returns the passages most similar to the question; a hazard
analysis of a targeted CSPP needs the whole narrative in reading order, or the
phase-specific paragraph that resembles no question is never seen.
"""

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from app.services.rag import MAX_DOCUMENT_CHUNKS, RAGService, _chunk_order

ORG = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _doc(source: str, index: int) -> dict[str, object]:
    return {
        "content": f"c{index}",
        "source": source,
        "source_type": "client",
        "section": f"Chunk {index + 1}",
        "chunk_id": f"{source}_{index}",
    }


async def _aiter(items: list[dict[str, object]]) -> AsyncIterator[dict[str, object]]:
    for item in items:
        yield item


def _service_returning(docs: list[dict[str, object]]) -> tuple[RAGService, AsyncMock]:
    service = RAGService(openai_client=AsyncMock())
    client = AsyncMock()
    client.search = AsyncMock(return_value=_aiter(docs))
    service._get_search_client = AsyncMock(return_value=client)  # type: ignore[method-assign]
    return service, client


def test_chunk_order_reads_the_indexer_suffix() -> None:
    assert _chunk_order("6f1c0a2e-0000-0000-0000-000000000000_12") == 12
    assert _chunk_order("legacy-id") == 0


@pytest.mark.asyncio
async def test_documents_come_back_in_reading_order_per_source() -> None:
    docs = [_doc("B.pdf", 1), _doc("A.pdf", 10), _doc("A.pdf", 2), _doc("B.pdf", 0)]
    service, client = _service_returning(docs)

    results = await service.fetch_documents(ORG, ["A.pdf", "B.pdf"])

    assert results is not None
    assert [(r.source, r.chunk_id) for r in results] == [
        ("A.pdf", "A.pdf_2"),
        ("A.pdf", "A.pdf_10"),
        ("B.pdf", "B.pdf_0"),
        ("B.pdf", "B.pdf_1"),
    ]
    assert all(r.retrieved_by == "document" and r.score == 1.0 for r in results)
    kwargs = client.search.call_args.kwargs
    assert kwargs["search_text"] == "*"
    assert "tenant_id eq" in kwargs["filter"]
    assert "source eq 'A.pdf'" in kwargs["filter"]
    assert kwargs["top"] == MAX_DOCUMENT_CHUNKS + 1


@pytest.mark.asyncio
async def test_a_document_over_the_budget_returns_none() -> None:
    service, _client = _service_returning([_doc("A.pdf", i) for i in range(4)])

    assert await service.fetch_documents(ORG, ["A.pdf"], max_chunks=3) is None


@pytest.mark.asyncio
async def test_no_sources_means_nothing_to_fetch() -> None:
    service, client = _service_returning([])

    assert await service.fetch_documents(ORG, []) == []
    client.search.assert_not_called()
