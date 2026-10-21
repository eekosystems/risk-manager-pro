"""What the audit log hands to its readers.

The API row and the CSV export both carry the entry's metadata, where the
before/after values and the originating chat live, and the timestamp keeps
its UTC offset so the page can show it in the reader's zone.
"""

import csv
import io
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from app.models.audit import AuditEntry
from app.schemas.audit import AuditEntryResponse
from app.services.audit_query import AuditQueryService


def _entry() -> AuditEntry:
    return AuditEntry(
        id=uuid.uuid4(),
        timestamp=datetime(2026, 10, 21, 14, 30, tzinfo=UTC),
        user_id=uuid.uuid4(),
        action="risk.updated",
        resource_type="risk_entry",
        resource_id="r-1",
        ip_address="10.0.0.1",
        user_agent="pytest",
        correlation_id=uuid.uuid4(),
        outcome="success",
        metadata_json={"changes": {"likelihood": {"old": "C", "new": "E"}}},
        organization_id=uuid.uuid4(),
    )


def test_api_row_exposes_metadata_and_keeps_the_offset() -> None:
    row = AuditEntryResponse.model_validate(_entry())

    assert row.metadata == {"changes": {"likelihood": {"old": "C", "new": "E"}}}
    assert row.timestamp.utcoffset() is not None
    assert row.model_dump(mode="json")["timestamp"] == "2026-10-21T14:30:00Z"


async def test_csv_export_includes_metadata_as_json() -> None:
    service = AuditQueryService(db=AsyncMock())
    repo = AsyncMock()
    repo.list_entries.return_value = ([_entry()], 1)
    service._repo = repo

    csv_text = await service.export_csv(organization_id=uuid.uuid4())

    header, row = list(csv.reader(io.StringIO(csv_text)))
    assert header[-1] == "metadata"
    assert row[-1] == json.dumps(
        {"changes": {"likelihood": {"old": "C", "new": "E"}}}, sort_keys=True
    )
