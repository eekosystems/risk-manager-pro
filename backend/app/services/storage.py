import structlog
from azure.core.exceptions import AzureError, ResourceExistsError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from app.core.config import settings

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
        self, blob_path: str, data: bytes, content_type: str, container: str | None = None
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
        await blob_client.upload_blob(data, content_type=content_type, overwrite=True)
        logger.info("blob_uploaded", path=blob_path, size=len(data))
        return blob_path

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
