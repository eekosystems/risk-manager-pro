"""Tests for the untrusted-document parsers.

Covers the spreadsheet path (previously untested, and the format the client was
blocked on) and the from-disk variants used for large uploads.
"""

import os
import tempfile
from collections.abc import Iterator

import pytest
from openpyxl import Workbook

from app.services.parser_sandbox import (
    extract_text_local,
    extract_text_local_from_path,
    run_sandboxed,
)

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _build_workbook_bytes() -> bytes:
    """A two-sheet workbook resembling an incident tracking log."""
    wb = Workbook()
    tracking = wb.active
    tracking.title = "Incident Tracking"
    tracking.append(["Date", "Location", "Event", "Injury"])
    tracking.append(["2026-08-01", "Terminal A", "Slip on wet floor", "Minor"])
    tracking.append(["2026-08-02", "Ramp", "Fuel truck collision", "None"])

    construction = wb.create_sheet("Construction Safety Reports")
    construction.append(["Date", "Contractor", "Finding"])
    construction.append(["2026-08-03", "Acme", "Gas line strike"])

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "wb.xlsx")
        wb.save(path)
        with open(path, "rb") as fh:
            return fh.read()


@pytest.fixture
def workbook_bytes() -> bytes:
    return _build_workbook_bytes()


@pytest.fixture
def workbook_path(workbook_bytes: bytes) -> Iterator[str]:
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    with os.fdopen(fd, "wb") as fh:
        fh.write(workbook_bytes)
    try:
        yield path
    finally:
        os.unlink(path)


def test_extract_xlsx_from_bytes_includes_all_sheets(workbook_bytes: bytes) -> None:
    text = extract_text_local(workbook_bytes, XLSX_CONTENT_TYPE)

    assert "--- Incident Tracking ---" in text
    assert "--- Construction Safety Reports ---" in text
    assert "Slip on wet floor" in text
    assert "Fuel truck collision" in text
    assert "Gas line strike" in text


def test_extract_xlsx_from_path_matches_bytes_extraction(
    workbook_bytes: bytes, workbook_path: str
) -> None:
    """The large-file path must produce the same text as the in-memory path."""
    from_bytes = extract_text_local(workbook_bytes, XLSX_CONTENT_TYPE)
    from_path = extract_text_local_from_path(workbook_path, XLSX_CONTENT_TYPE)

    assert from_path == from_bytes


def test_extract_text_from_path_plain_text() -> None:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("hazard report line one\nhazard report line two")
    try:
        assert extract_text_local_from_path(path, "text/plain") == (
            "hazard report line one\nhazard report line two"
        )
    finally:
        os.unlink(path)


def test_unsupported_content_type_raises_in_both_variants(workbook_path: str) -> None:
    with pytest.raises(ValueError, match="Unsupported content type"):
        extract_text_local(b"data", "image/png")
    with pytest.raises(ValueError, match="Unsupported content type"):
        extract_text_local_from_path(workbook_path, "image/png")


def test_run_sandboxed_executes_parser_out_of_process(workbook_bytes: bytes) -> None:
    """The parser actually runs through the subprocess wrapper, not just inline."""
    text = run_sandboxed(extract_text_local, workbook_bytes, XLSX_CONTENT_TYPE)

    assert "Slip on wet floor" in text
