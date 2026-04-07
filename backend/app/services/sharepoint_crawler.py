"""SharePoint document crawler using Microsoft Graph API with client credentials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import msal  # type: ignore[import-untyped]
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


@dataclass
class SharePointFile:
    """Metadata for a file discovered in SharePoint."""

    drive_item_id: str
    name: str
    size: int
    content_type: str
    web_url: str
    drive_id: str
    folder_path: str


class SharePointCrawler:
    """Crawl a SharePoint site via Microsoft Graph using client credentials flow."""

    def __init__(self) -> None:
        self._app: msal.ConfidentialClientApplication | None = None
        self._client: httpx.AsyncClient | None = None
        self._site_id: str | None = None

    def _ensure_app(self) -> msal.ConfidentialClientApplication:
        if self._app is None:
            if not settings.sharepoint_client_id or not settings.sharepoint_client_secret:
                raise RuntimeError(
                    "SharePoint credentials not configured. "
                    "Set SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, and SHAREPOINT_CLIENT_SECRET."
                )
            authority = f"https://login.microsoftonline.com/{settings.sharepoint_tenant_id}"
            self._app = msal.ConfidentialClientApplication(
                client_id=settings.sharepoint_client_id,
                client_credential=settings.sharepoint_client_secret,
                authority=authority,
            )
        return self._app

    async def _get_token(self) -> str:
        app = self._ensure_app()
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown error"))
            raise RuntimeError(f"Failed to acquire SharePoint token: {error}")
        token: str = result["access_token"]
        return token

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def _graph_get(self, url: str) -> dict[str, Any]:
        """Make an authenticated GET request to Microsoft Graph."""
        client = await self._ensure_client()
        token = await self._get_token()
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code >= 400:
            logger.error(
                "sharepoint_graph_error",
                url=url,
                status=response.status_code,
                body=response.text[:500],
            )
            raise RuntimeError(
                f"Graph API request failed (HTTP {response.status_code}): {response.text[:200]}"
            )
        result: dict[str, Any] = response.json()
        return result

    async def _get_site_id(self) -> str:
        """Resolve the SharePoint site URL to a Graph site ID."""
        if self._site_id:
            return self._site_id

        parsed = urlparse(settings.sharepoint_site_url)
        hostname = parsed.hostname
        site_path = parsed.path

        if not hostname or not site_path:
            raise ValueError(
                f"Invalid SharePoint site URL: {settings.sharepoint_site_url}. "
                "Expected format: https://tenant.sharepoint.com/sites/SiteName"
            )

        url = f"{GRAPH_BASE_URL}/sites/{hostname}:{site_path}"
        data = await self._graph_get(url)
        site_id: str = data["id"]
        self._site_id = site_id
        logger.info("sharepoint_site_resolved", site_id=site_id, hostname=hostname)
        return site_id

    async def list_drives(self) -> list[dict[str, Any]]:
        """List document libraries (drives) in the SharePoint site."""
        site_id = await self._get_site_id()
        data = await self._graph_get(f"{GRAPH_BASE_URL}/sites/{site_id}/drives")
        drives: list[dict[str, Any]] = data.get("value", [])
        logger.info("sharepoint_drives_listed", count=len(drives))
        return drives

    async def _list_folder_items(
        self,
        drive_id: str,
        folder_path: str = "",
    ) -> list[SharePointFile]:
        """Recursively list supported files in a drive or folder."""
        if folder_path:
            url = f"{GRAPH_BASE_URL}/drives/{drive_id}/root:/{folder_path}:/children"
        else:
            url = f"{GRAPH_BASE_URL}/drives/{drive_id}/root/children"

        files: list[SharePointFile] = []
        while url:
            data = await self._graph_get(url)
            for item in data.get("value", []):
                name: str = item.get("name", "")
                if "folder" in item:
                    child_path = f"{folder_path}/{name}" if folder_path else name
                    sub_files = await self._list_folder_items(drive_id, child_path)
                    files.extend(sub_files)
                elif "file" in item:
                    ext = _get_extension(name)
                    if ext in SUPPORTED_EXTENSIONS:
                        content_type = EXTENSION_TO_CONTENT_TYPE.get(
                            ext, item.get("file", {}).get("mimeType", "application/octet-stream")
                        )
                        files.append(
                            SharePointFile(
                                drive_item_id=item["id"],
                                name=name,
                                size=item.get("size", 0),
                                content_type=content_type,
                                web_url=item.get("webUrl", ""),
                                drive_id=drive_id,
                                folder_path=folder_path or "/",
                            )
                        )
            url = data.get("@odata.nextLink", "")

        return files

    async def discover_files(self, drive_name: str | None = None) -> list[SharePointFile]:
        """Discover all supported files across drives (or a specific drive)."""
        drives = await self.list_drives()
        files: list[SharePointFile] = []

        for drive in drives:
            if drive_name and drive.get("name", "").lower() != drive_name.lower():
                continue
            drive_id = drive["id"]
            drive_files = await self._list_folder_items(drive_id)
            logger.info(
                "sharepoint_drive_scanned",
                drive_name=drive.get("name"),
                file_count=len(drive_files),
            )
            files.extend(drive_files)

        logger.info("sharepoint_discovery_complete", total_files=len(files))
        return files

    async def download_file(self, file: SharePointFile) -> bytes:
        """Download a file's content from SharePoint."""
        client = await self._ensure_client()
        token = await self._get_token()

        url = f"{GRAPH_BASE_URL}/drives/{file.drive_id}/items/{file.drive_item_id}/content"
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=True,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to download {file.name} (HTTP {response.status_code})")

        logger.info(
            "sharepoint_file_downloaded",
            filename=file.name,
            size_bytes=len(response.content),
        )
        return response.content

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


def _get_extension(filename: str) -> str:
    """Extract lowercase file extension including the dot."""
    match = re.search(r"\.\w+$", filename)
    return match.group(0).lower() if match else ""
