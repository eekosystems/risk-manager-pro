"""Tests for RAG grounding detection in the chat service.

Regression cover for the failure seen on the SAT dataset: the user named two
documents, retrieval returned chunks from *other* documents, and the model
described the named files' contents anyway while reporting high confidence.
Retrieval falling back to an unfiltered search must never be silent.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.chat import (
    ChatService,
    _build_context_block,
    _build_grounding_notice,
    _resolve_grounding,
)
from app.services.rag import SearchResult
from tests.conftest import ORGANIZATION_ID

CONVERSATION_ID = uuid.UUID("00000000-0000-0000-0000-0000000000aa")


def _result(source: str, content: str = "chunk text") -> SearchResult:
    return SearchResult(
        content=content,
        source=source,
        source_type="client",
        section=None,
        score=0.03,
        chunk_id=f"{source}_0",
    )


@pytest.fixture
def chat_service() -> ChatService:
    return ChatService(
        db=AsyncMock(),
        openai_client=AsyncMock(),
        rag_service=AsyncMock(),
        settings_service=AsyncMock(),
    )


# --- Grounding verdict --------------------------------------------------------


def test_no_requested_sources_is_not_a_miss() -> None:
    grounding = _resolve_grounding([], [_result("Anything.pdf")])

    assert grounding.is_miss is False
    assert grounding.requested_sources == []


def test_requested_source_present_in_results_is_not_a_miss() -> None:
    grounding = _resolve_grounding(
        ["SAT_Tracking.pdf"], [_result("SAT_Tracking.pdf"), _result("Other.pdf")]
    )

    assert grounding.is_miss is False
    assert grounding.matched_sources == ["SAT_Tracking.pdf"]
    assert grounding.missing_sources == []


def test_partial_miss_flags_only_the_document_that_was_not_retrieved() -> None:
    """Retrieving one of two named files still leaves the other open to invention."""
    grounding = _resolve_grounding(
        ["SAT_Tracking.pdf", "SAT_Events.pdf"], [_result("SAT_Tracking.pdf")]
    )

    assert grounding.is_miss is True
    assert grounding.matched_sources == ["SAT_Tracking.pdf"]
    assert grounding.missing_sources == ["SAT_Events.pdf"]
    assert "SAT_Events.pdf" in _build_grounding_notice(grounding)
    assert "SAT_Tracking.pdf" not in _build_grounding_notice(grounding)


def test_requested_source_absent_from_results_is_a_miss() -> None:
    """The SAT failure: results came back, but from unrelated documents."""
    grounding = _resolve_grounding(
        ["SAT_Tracking.pdf", "SAT_Events.pdf"],
        [_result("Prior_SRA_Report.pdf"), _result("ASEIP_CSPP.pdf")],
    )

    assert grounding.is_miss is True
    assert grounding.matched_sources == []
    assert grounding.missing_sources == ["SAT_Tracking.pdf", "SAT_Events.pdf"]


def test_source_matching_ignores_case() -> None:
    grounding = _resolve_grounding(["sat_tracking.PDF"], [_result("SAT_Tracking.pdf")])

    assert grounding.is_miss is False


def test_empty_results_with_requested_sources_is_a_miss() -> None:
    grounding = _resolve_grounding(["SAT_Tracking.pdf"], [])

    assert grounding.is_miss is True


# --- What the model is told ---------------------------------------------------


def test_context_block_warns_the_model_on_a_grounding_miss() -> None:
    grounding = _resolve_grounding(["SAT_Tracking.pdf"], [_result("Prior_SRA_Report.pdf")])

    block = _build_context_block([_result("Prior_SRA_Report.pdf")], grounding)

    assert "GROUNDING FAILURE" in block
    assert "SAT_Tracking.pdf" in block
    # It must forbid describing unseen files and force confidence down.
    assert "NOT describe" in block
    assert "'Low'" in block
    # The retrieved material is still supplied, still fenced as untrusted.
    assert "<reference_documents>" in block


def test_context_block_is_unchanged_when_grounding_is_fine() -> None:
    grounding = _resolve_grounding(["SAT_Tracking.pdf"], [_result("SAT_Tracking.pdf")])

    block = _build_context_block([_result("SAT_Tracking.pdf")], grounding)

    assert "GROUNDING FAILURE" not in block
    assert "<reference_documents>" in block


def test_grounding_notice_names_every_missed_document() -> None:
    grounding = _resolve_grounding(["A.pdf", "B.pdf"], [_result("C.pdf")])

    notice = _build_grounding_notice(grounding)

    assert "not grounded" in notice
    assert "- A.pdf" in notice
    assert "- B.pdf" in notice


# --- Retrieval behavior -------------------------------------------------------


@pytest.mark.asyncio
async def test_exact_filter_miss_retries_against_fuzzy_candidates(
    chat_service: ChatService,
) -> None:
    """A typed name that doesn't byte-match the stored name must still resolve."""
    stored = "Airport_Safety_Tracking_20260812.pdf"
    calls: list[list[str] | None] = []

    async def _search(_q: str, **kwargs: object) -> list[SearchResult]:
        source_filter = kwargs.get("source_filter")
        calls.append(source_filter)  # type: ignore[arg-type]
        if source_filter == [stored]:
            return [_result(stored)]
        return []

    chat_service._rag.hybrid_search = AsyncMock(side_effect=_search)  # type: ignore[method-assign]

    results, block, grounding = await chat_service._build_rag_context(
        query="summarize AirportSafetyTracking_20260812.pdf",
        organization_id=ORGANIZATION_ID,
        conversation_id=CONVERSATION_ID,
        top_k=5,
        score_threshold=0.0,
        candidate_filenames=[stored],
    )

    assert [r.source for r in results] == [stored]
    assert grounding.is_miss is False
    assert "GROUNDING FAILURE" not in block
    # First the literal typed name, then the real indexed filename.
    assert calls[0] == ["AirportSafetyTracking_20260812.pdf"]
    assert calls[1] == [stored]


@pytest.mark.asyncio
async def test_unfiltered_fallback_is_reported_as_a_miss(chat_service: ChatService) -> None:
    """The exact SAT scenario: fallback returns other documents' chunks."""

    async def _search(_q: str, **kwargs: object) -> list[SearchResult]:
        if kwargs.get("source_filter"):
            return []
        return [_result("Prior_SRA_Report.pdf")]

    chat_service._rag.hybrid_search = AsyncMock(side_effect=_search)  # type: ignore[method-assign]

    results, block, grounding = await chat_service._build_rag_context(
        query="run a system analysis on SAT_Tracking.pdf",
        organization_id=ORGANIZATION_ID,
        conversation_id=CONVERSATION_ID,
        top_k=5,
        score_threshold=0.0,
    )

    assert [r.source for r in results] == ["Prior_SRA_Report.pdf"]
    assert grounding.is_miss is True
    assert grounding.requested_sources == ["SAT_Tracking.pdf"]
    assert "GROUNDING FAILURE" in block


@pytest.mark.asyncio
async def test_untargeted_query_never_reports_a_miss(chat_service: ChatService) -> None:
    """Ordinary questions that name no file must not trigger the warning."""
    chat_service._rag.hybrid_search = AsyncMock(  # type: ignore[method-assign]
        return_value=[_result("Some_Doc.pdf")]
    )

    _results, block, grounding = await chat_service._build_rag_context(
        query="what does Part 139 require for self-inspection?",
        organization_id=ORGANIZATION_ID,
        conversation_id=CONVERSATION_ID,
        top_k=5,
        score_threshold=0.0,
    )

    assert grounding.is_miss is False
    assert "GROUNDING FAILURE" not in block


@pytest.mark.asyncio
async def test_rag_failure_still_reports_a_miss_for_targeted_queries(
    chat_service: ChatService,
) -> None:
    """If search itself errors, a named-document request is still ungrounded."""
    chat_service._rag.hybrid_search = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("search unavailable")
    )

    results, _block, grounding = await chat_service._build_rag_context(
        query="analyze SAT_Tracking.pdf",
        organization_id=ORGANIZATION_ID,
        conversation_id=CONVERSATION_ID,
        top_k=5,
        score_threshold=0.0,
    )

    assert results == []
    assert grounding.is_miss is True
