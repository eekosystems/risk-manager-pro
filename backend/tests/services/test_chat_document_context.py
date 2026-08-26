"""Resolving what the user asked for, separately from what retrieval filters by.

Regression cover for the TW V RON run: the CSPP was still indexing, every
realistic way of asking for it quietly swapped in a different project's CSPP,
and the output was a generic analysis dressed as a grounded one — with no
notice. A requested document that cannot be retrieved must be reported, never
replaced.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.conversation import FunctionType
from app.models.document import Document, DocumentStatus
from app.schemas.chat import ChatRequest
from app.services.chat import (
    _FG_NO_MATCH_BANNER,
    ChatService,
    _build_grounding_notice,
    _detect_missing_mandatory_elements,
    _fg_no_match_banner,
    _find_filenames_in_query,
    _normalize_filename,
    _resolve_grounding,
)
from app.services.rag import SearchResult
from tests.conftest import ORGANIZATION_ID

CONVERSATION_ID = uuid.UUID("00000000-0000-0000-0000-0000000000bb")

TWV = "20250112_TW_V_RON_CSPP_Narr_and_Plan_Update_-_July_2026.pdf"
CARGO = "PVDS_Cargo_Ramp_Development_-_CSPP_Narrative.pdf"
GATES = "PVDGates_7_and_8_CSPP_Narrative_IFC_Bulletin_3_20260410_-_July_2026.pdf"


def _doc(filename: str, status: DocumentStatus, doc_id: uuid.UUID | None = None) -> Document:
    return Document(
        id=doc_id or uuid.uuid4(),
        organization_id=ORGANIZATION_ID,
        uploaded_by=uuid.uuid4(),
        filename=filename,
        blob_path=f"{ORGANIZATION_ID}/{filename}",
        content_type="application/pdf",
        size_bytes=1,
        status=status,
    )


def _result(source: str, source_type: str = "client") -> SearchResult:
    return SearchResult(
        content="chunk text",
        source=source,
        source_type=source_type,
        section=None,
        score=0.03,
        chunk_id=f"{source}_0",
    )


@pytest.fixture
def chat_service() -> ChatService:
    service = ChatService(
        db=AsyncMock(),
        openai_client=AsyncMock(),
        rag_service=AsyncMock(),
        settings_service=AsyncMock(),
    )
    service._doc_repo = AsyncMock()
    return service


def _stub_documents(service: ChatService, recent: list[Document], indexed: list[str]) -> None:
    service._doc_repo.list_recent_documents = AsyncMock(return_value=recent)  # type: ignore[method-assign]
    service._doc_repo.list_indexed_filenames = AsyncMock(return_value=indexed)  # type: ignore[method-assign]


# --- Filename identity --------------------------------------------------------


def test_normalized_filenames_ignore_separators_and_case() -> None:
    assert _normalize_filename("Airport Safety Tracking.pdf") == _normalize_filename(
        "airport_safety_tracking.PDF"
    )
    assert _normalize_filename(CARGO) != _normalize_filename(GATES)


def test_a_full_filename_typed_with_spaces_is_found_in_the_query() -> None:
    query = (
        "Create a hazard assessment for 20250112 TW V RON CSPP Narr and Plan Update - July 2026.pdf"
    )

    assert _find_filenames_in_query(query, [TWV, CARGO, GATES]) == [TWV]


def test_short_stems_are_not_resolved_by_substring() -> None:
    """ "SRA" and "report" occur in ordinary prose; matching them would be noise."""
    assert _find_filenames_in_query("run the sra report", ["SRA.pdf", "Report.pdf"]) == []


# --- Request resolution -------------------------------------------------------


@pytest.mark.asyncio
async def test_a_session_upload_still_processing_is_requested_not_replaced(
    chat_service: ChatService,
) -> None:
    """The TW V RON case: "the file I just uploaded" while it is still indexing."""
    upload_id = uuid.uuid4()
    _stub_documents(
        chat_service,
        recent=[
            _doc(TWV, DocumentStatus.PROCESSING, upload_id),
            _doc(CARGO, DocumentStatus.INDEXED),
        ],
        indexed=[CARGO, GATES],
    )
    request = ChatRequest(
        message="Create a hazard assessment for the file I just uploaded",
        recent_upload_ids=[upload_id],
    )

    docs = await chat_service._resolve_document_context(request, ORGANIZATION_ID)

    assert docs.requested_sources == [TWV]
    assert docs.unindexed_sources == [TWV]
    assert docs.source_filter == []


@pytest.mark.asyncio
async def test_a_name_typed_with_spaces_resolves_to_the_stored_document(
    chat_service: ChatService,
) -> None:
    """`_FILENAME_RE` alone sees only "2026.pdf" here, which matches nothing."""
    _stub_documents(
        chat_service,
        recent=[_doc(TWV, DocumentStatus.PROCESSING)],
        indexed=[CARGO, GATES],
    )
    request = ChatRequest(
        message=(
            "Create a hazard assessment for 20250112 TW V RON CSPP Narr and Plan "
            "Update - July 2026.pdf"
        )
    )

    docs = await chat_service._resolve_document_context(request, ORGANIZATION_ID)

    assert docs.requested_sources == [TWV]
    assert docs.unindexed_sources == [TWV]
    assert "2026.pdf" not in docs.requested_sources


@pytest.mark.asyncio
async def test_pronoun_reference_targets_the_latest_upload_whatever_its_status(
    chat_service: ChatService,
) -> None:
    _stub_documents(
        chat_service,
        recent=[_doc(TWV, DocumentStatus.PROCESSING), _doc(CARGO, DocumentStatus.INDEXED)],
        indexed=[CARGO],
    )
    request = ChatRequest(message="summarize the most recent upload")

    docs = await chat_service._resolve_document_context(request, ORGANIZATION_ID)

    assert docs.requested_sources == [TWV]
    assert docs.unindexed_sources == [TWV]


@pytest.mark.asyncio
async def test_an_indexed_document_named_in_the_query_becomes_the_filter(
    chat_service: ChatService,
) -> None:
    _stub_documents(chat_service, recent=[], indexed=[CARGO, GATES])
    request = ChatRequest(message="summarize PVDS Cargo Ramp Development - CSPP Narrative.pdf")

    docs = await chat_service._resolve_document_context(request, ORGANIZATION_ID)

    assert docs.source_filter == [CARGO]
    assert docs.requested_sources == [CARGO]
    assert docs.unindexed_sources == []


@pytest.mark.asyncio
async def test_a_single_token_candidate_becomes_the_filter(chat_service: ChatService) -> None:
    _stub_documents(chat_service, recent=[], indexed=[GATES, CARGO])
    request = ChatRequest(message="tell me about the IFC bulletin")

    docs = await chat_service._resolve_document_context(request, ORGANIZATION_ID)

    assert docs.candidates == [GATES]
    assert docs.source_filter == [GATES]
    assert docs.requested_sources == [GATES]


@pytest.mark.asyncio
async def test_an_unknown_typed_filename_is_searched_literally_and_stays_requested(
    chat_service: ChatService,
) -> None:
    _stub_documents(chat_service, recent=[], indexed=[])
    request = ChatRequest(message="analyze SAT_Tracking.pdf")

    docs = await chat_service._resolve_document_context(request, ORGANIZATION_ID)

    assert docs.source_filter == ["SAT_Tracking.pdf"]
    assert docs.requested_sources == ["SAT_Tracking.pdf"]
    assert docs.unindexed_sources == []


# --- Retrieval never rewrites the request ------------------------------------


@pytest.mark.asyncio
async def test_a_fuzzy_retry_landing_on_a_different_document_is_a_miss(
    chat_service: ChatService,
) -> None:
    """The retry exists for spelling differences, not for substituting projects."""

    async def _search(_q: str, **kwargs: object) -> list[SearchResult]:
        if kwargs.get("source_filter") == [CARGO]:
            return [_result(CARGO)]
        return []

    chat_service._rag.hybrid_search = AsyncMock(side_effect=_search)  # type: ignore[method-assign]

    results, block, grounding = await chat_service._build_rag_context(
        query="Create a hazard assessment for the TW V RON CSPP",
        organization_id=ORGANIZATION_ID,
        conversation_id=CONVERSATION_ID,
        top_k=5,
        score_threshold=0.0,
        candidate_filenames=[CARGO],
        source_filter=[TWV],
        requested_sources=[TWV],
    )

    assert [r.source for r in results] == [CARGO]
    assert grounding.is_miss is True
    assert grounding.missing_sources == [TWV]
    assert "GROUNDING FAILURE" in block


@pytest.mark.asyncio
async def test_an_unindexed_request_is_a_miss_even_when_search_returns_content(
    chat_service: ChatService,
) -> None:
    chat_service._rag.hybrid_search = AsyncMock(return_value=[_result(CARGO)])  # type: ignore[method-assign]

    _results, block, grounding = await chat_service._build_rag_context(
        query="Create a hazard assessment for the file I just uploaded",
        organization_id=ORGANIZATION_ID,
        conversation_id=CONVERSATION_ID,
        top_k=5,
        score_threshold=0.0,
        source_filter=[],
        requested_sources=[TWV],
        unindexed_sources=[TWV],
    )

    assert grounding.is_miss is True
    assert grounding.unindexed_sources == [TWV]
    assert "not yet indexed" in block


def test_the_notice_says_why_an_unindexed_document_was_not_retrieved() -> None:
    grounding = _resolve_grounding([], [_result(CARGO)], unindexed_sources=[TWV])

    notice = _build_grounding_notice(grounding)

    assert f"- {TWV} — not yet indexed" in notice


def test_grounding_matches_by_normalized_name() -> None:
    grounding = _resolve_grounding(
        ["Airport Safety Tracking 20260812.pdf"],
        [_result("Airport_Safety_Tracking_20260812.pdf")],
    )

    assert grounding.is_miss is False


# --- Inline citations ---------------------------------------------------------


def test_missing_inline_citations_are_reported_when_sources_were_retrieved() -> None:
    content = "### Answer\nThe CSPP requires barricades.\nConfidence Level: Moderate."

    missing = _detect_missing_mandatory_elements(content, FunctionType.PHL, has_sources=True)

    assert "Inline Source Citations" in missing


def test_inline_citations_are_not_required_without_retrieved_sources() -> None:
    content = "### Answer\nNo documents were available."

    missing = _detect_missing_mandatory_elements(content, FunctionType.PHL, has_sources=False)

    assert "Inline Source Citations" not in missing


def test_inline_citations_satisfy_the_check() -> None:
    content = "The CSPP requires barricades [Source 2]."

    missing = _detect_missing_mandatory_elements(content, FunctionType.PHL, has_sources=True)

    assert "Inline Source Citations" not in missing


def test_general_turns_have_no_citation_requirement() -> None:
    assert _detect_missing_mandatory_elements("hi", FunctionType.GENERAL, has_sources=True) == []


# --- FG precedent banner ------------------------------------------------------


def test_analysis_without_fg_precedent_gets_the_verbatim_banner() -> None:
    banner = _fg_no_match_banner(FunctionType.SRA, [_result(CARGO, "client")])

    assert banner.startswith(_FG_NO_MATCH_BANNER)
    assert "No FG SRM precedent identified for this airport/context." in banner


def test_an_fg_document_in_the_results_suppresses_the_banner() -> None:
    results = [_result(CARGO, "client"), _result("FG_SRA_KSAT_2024.pdf", "internal")]

    assert _fg_no_match_banner(FunctionType.SRA, results) == ""


def test_conversational_turns_never_get_the_banner() -> None:
    assert _fg_no_match_banner(FunctionType.GENERAL, [_result(CARGO)]) == ""
    assert _fg_no_match_banner(FunctionType.RISK_REGISTER, [_result(CARGO)]) == ""
