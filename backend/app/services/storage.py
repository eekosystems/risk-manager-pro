import base64
from collections.abc import AsyncIterator

import structlog
from azure.core.exceptions import AzureError, ResourceExistsError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import BlobBlock, ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from app.core.config import settings
from app.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)


class BlobStorageService:
    def __init__(self) -> None:
        self._client: BlobServiceClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            if settings.azure_storage_account_name:
                self._credential = DefaultAzureCredential()
                account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
                self._client = BlobServiceClient(
                    account_url=account_url, credential=self._credential
                )
            elif settings.app_env == "development":
                conn_str = settings.azure_storage_connection_string
                if not conn_str:
                    raise RuntimeError(
                        "AZURE_STORAGE_CONNECTION_STRING must be set for local development"
                    )
                self._client = BlobServiceClient.from_connection_string(conn_str)
            else:
                raise RuntimeError(
                    "AZURE_STORAGE_ACCOUNT_NAME is required in non-development environments"
                )
        return self._client

    async def upload(
        self,
        blob_path: str,
        data: bytes,
        content_type: str,
        container: str | None = None,
        overwrite: bool = True,
    ) -> str:
        client = await self._get_client()
        container_name = container or settings.azure_storage_container_name
        container_client = client.get_container_client(container_name)

        try:
            await container_client.create_container()
        except ResourceExistsError:
            pass  # Container already exists
        except AzureError as e:
            logger.warning("container_create_failed", container=container_name, error=str(e))

        blob_client = container_client.get_blob_client(blob_path)
        await blob_client.upload_blob(data, content_type=content_type, overwrite=overwrite)
        logger.info("blob_uploaded", path=blob_path, size=len(data))
        return blob_path

    async def upload_stream(
        self,
        blob_path: str,
        chunks: AsyncIterator[bytes],
        content_type: str,
        *,
        max_bytes: int,
        container: str | None = None,
    ) -> int:
        """Stream chunks into a block blob without buffering the whole file.

        Each chunk is staged as a block and the block list is committed at the
        end, so peak memory is roughly one chunk — this is what makes multi-GB
        uploads survivable on a small container. Returns the total bytes
        written. Raises ValidationError (without committing the blob) if the
        stream exceeds max_bytes or is empty; uncommitted blocks are garbage
        collected by Azure, so a rejected upload leaves nothing behind.
        """
        client = await self._get_client()
        container_name = container or settings.azure_storage_container_name
        await self._ensure_container(container_name)
        blob_client = client.get_container_client(container_name).get_blob_client(blob_path)

        block_ids: list[str] = []
        total = 0
        index = 0
        async for chunk in chunks:
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValidationError(
                    f"File exceeds maximum size of {max_bytes // (1024 * 1024)} MB"
                )
            # Block IDs must be equal-length, base64-encoded strings.
            block_id = base64.b64encode(f"{index:08d}".encode()).decode()
            await blob_client.stage_block(block_id, chunk)
            block_ids.append(block_id)
            index += 1

        if total == 0:
            raise ValidationError("Uploaded file is empty")

        await blob_client.commit_block_list(
            [BlobBlock(block_id=bid) for bid in block_ids],
            content_settings=ContentSettings(content_type=content_type),
        )
        logger.info("blob_stream_uploaded", path=blob_path, size=total, blocks=len(block_ids))
        return total

    async def _ensure_container(self, container_name: str) -> None:
        client = await self._get_client()
        container_client = client.get_container_client(container_name)
        try:
            await container_client.create_container()
        except ResourceExistsError:
            pass
        except AzureError as e:
            logger.warning("container_create_failed", container=container_name, error=str(e))

    async def download_head(self, blob_path: str, n: int, container: str | None = None) -> bytes:
        """Download only the first n bytes of a blob (for magic-byte validation)."""
        client = await self._get_client()
        container_name = container or settings.azure_storage_container_name
        blob_client = client.get_blob_client(container_name, blob_path)
        stream = await blob_client.download_blob(offset=0, length=n)
        return await stream.readall()

    async def download_to_path(
        self, blob_path: str, dest_path: str, container: str | None = None
    ) -> None:
        """Stream a blob to a local file without holding it all in memory."""
        client = await self._get_client()
        container_name = container or settings.azure_storage_container_name
        blob_client = client.get_blob_client(container_name, blob_path)
        stream = await blob_client.download_blob()
        with open(dest_path, "wb") as fh:
            async for chunk in stream.chunks():
                fh.write(chunk)

    async def download(self, blob_path: str, container: str | None = None) -> bytes:
        client = await self._get_client()
        container_name = container or settings.azure_storage_container_name
        blob_client = client.get_blob_client(container_name, blob_path)
        stream = await blob_client.download_blob()
        return await stream.readall()

    async def delete(self, blob_path: str, container: str | None = None) -> None:
        client = await self._get_client()
        container_name = container or settings.azure_storage_container_name
        blob_client = client.get_blob_client(container_name, blob_path)
        await blob_client.delete_blob()
        logger.info("blob_deleted", path=blob_path)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        if self._credential:
            await self._credential.close()
