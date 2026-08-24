"""Tests for the streaming blob upload used by large-file ingestion.

`upload_stream` is what the /documents/upload endpoint calls, so its size cap,
block staging, and commit behavior are on the hot path for every upload.
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.services.storage import BlobStorageService


async def _chunks(*payloads: bytes) -> AsyncIterator[bytes]:
    for payload in payloads:
        yield payload


@pytest.fixture
def storage() -> tuple[BlobStorageService, AsyncMock]:
    """A storage service wired to a fake blob client, plus that blob client."""
    service = BlobStorageService()
    blob_client = AsyncMock()

    container_client = MagicMock()
    container_client.get_blob_client.return_value = blob_client
    client = MagicMock()
    client.get_container_client.return_value = container_client

    async def _get_client() -> MagicMock:
        return client

    async def _ensure_container(_name: str) -> None:
        return None

    service._get_client = _get_client  # type: ignore[method-assign]
    service._ensure_container = _ensure_container  # type: ignore[method-assign]
    return service, blob_client


@pytest.mark.asyncio
async def test_upload_stream_stages_each_chunk_and_commits(
    storage: tuple[BlobStorageService, AsyncMock],
) -> None:
    service, blob_client = storage

    total = await service.upload_stream(
        "org/doc/report.pdf",
        _chunks(b"aaa", b"bbbb", b"cc"),
        "application/pdf",
        max_bytes=1_000,
    )

    assert total == 9
    assert blob_client.stage_block.await_count == 3
    blob_client.commit_block_list.assert_awaited_once()

    # Block IDs must be unique and equal-length, or Azure rejects the commit.
    staged_ids = [call.args[0] for call in blob_client.stage_block.await_args_list]
    assert len(set(staged_ids)) == 3
    assert len({len(bid) for bid in staged_ids}) == 1


@pytest.mark.asyncio
async def test_upload_stream_rejects_oversize_mid_stream_without_committing(
    storage: tuple[BlobStorageService, AsyncMock],
) -> None:
    """The cap must trip during the stream, not after the whole file lands."""
    service, blob_client = storage

    with pytest.raises(ValidationError, match="exceeds maximum size"):
        await service.upload_stream(
            "org/doc/huge.pdf",
            _chunks(b"x" * 6, b"x" * 6, b"x" * 6),
            "application/pdf",
            max_bytes=10,
        )

    blob_client.commit_block_list.assert_not_awaited()
    # It stopped as soon as the cap was crossed rather than staging everything.
    assert blob_client.stage_block.await_count == 1


@pytest.mark.asyncio
async def test_upload_stream_rejects_empty_upload(
    storage: tuple[BlobStorageService, AsyncMock],
) -> None:
    service, blob_client = storage

    with pytest.raises(ValidationError, match="empty"):
        await service.upload_stream(
            "org/doc/empty.pdf", _chunks(b"", b""), "application/pdf", max_bytes=1_000
        )

    blob_client.commit_block_list.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_stream_accepts_a_stream_larger_than_memory_chunking(
    storage: tuple[BlobStorageService, AsyncMock],
) -> None:
    """Many chunks commit as many blocks — the multi-GB shape, scaled down."""
    service, blob_client = storage
    chunk = b"x" * 1024

    total = await service.upload_stream(
        "org/doc/big.pdf",
        _chunks(*([chunk] * 500)),
        "application/pdf",
        max_bytes=1024 * 1024,
    )

    assert total == 512_000
    assert blob_client.stage_block.await_count == 500
    committed_blocks = blob_client.commit_block_list.await_args.args[0]
    assert len(committed_blocks) == 500
