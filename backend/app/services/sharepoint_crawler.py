"""SharePoint document crawler using Microsoft Graph API with client credentials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import httpx
import msal
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


# Normalize away spaces/dashes/underscores + case so matchers don't break
# when folder names vary slightly between airports (e.g. "risk-outcome" vs
# "Risk Outcome" vs "risk_outcome").
def normalize_folder_name(name: str) -> str:
    return re.sub(r"[\s\-_]+", "", name or "").lower()


RISK_OUTCOME_NORMALIZED = "riskoutcome"


def is_risk_outcome_folder(name: str) -> bool:
    return normalize_folder_name(name) == RISK_OUTCOME_NORMALIZED


def _graph_path_url(drive_id: str, path: str, suffix: str = "children") -> str:
    """Build a Graph path-addressed URL with each segment percent-encoded.

    Graph addresses items by path via `/drives/{id}/root:/{path}:/{suffix}`.
    Path segments frequently contain spaces or other reserved characters
    (e.g. "RMP Master Directory", "Airport - Safety Risk Management
    Documents") that MUST be percent-encoded before being sent to Graph,
    while the `:` separators and the `/` between segments must remain
    unescaped. Passing raw spaces/specials silently yields empty results.
    """
    cleaned = (path or "").strip("/")
    if not cleaned:
        return f"{GRAPH_BASE_URL}/drives/{drive_id}/root/{suffix}"
    encoded_path = "/".join(quote(seg, safe="") for seg in cleaned.split("/") if seg)
    return f"{GRAPH_BASE_URL}/drives/{drive_id}/root:/{encoded_path}:/{suffix}"


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".csv", ".xlsx", ".pptx"}

EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
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
        """Recursively list supported files in a drive or folder.

        Errors on any single subfolder (a 403, 404, timeout, rate-limit,
        etc.) are logged and swallowed so the recursion continues into
        sibling folders. Without this isolation, one broken subfolder
        aborts the entire walk and silently drops every airport that
        comes after it in traversal order.
        """
        url = _graph_path_url(drive_id, folder_path)

        files: list[SharePointFile] = []
        while url:
            try:
                data = await self._graph_get(url)
            except Exception:  # noqa: BLE001 — never kill the wider walk on one HTTP error
                logger.warning(
                    "sharepoint_list_folder_failed",
                    folder_path=folder_path or "<drive root>",
                    exc_info=True,
                )
                break

            for item in data.get("value", []):
                name: str = item.get("name", "")
                if "folder" in item:
                    child_path = f"{folder_path}/{name}" if folder_path else name
                    try:
                        sub_files = await self._list_folder_items(drive_id, child_path)
                    except Exception:  # noqa: BLE001 — isolate per-child recursion errors
                        logger.warning(
                            "sharepoint_subfolder_walk_failed",
                            folder_path=child_path,
                            exc_info=True,
                        )
                        continue
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

    async def discover_folder(self, folder_path: str) -> list[SharePointFile]:
        """Discover files in a specific folder path across all drives."""
        drives = await self.list_drives()
        files: list[SharePointFile] = []
        for drive in drives:
            drive_id = drive["id"]
            drive_files = await self._list_folder_items(drive_id, folder_path)
            files.extend(drive_files)
        logger.info(
            "sharepoint_folder_scanned",
            folder_path=folder_path,
            file_count=len(files),
        )
        return files

    async def list_airport_folders(self, drive_name: str | None = None) -> list[str]:
        """Return every airport folder name inside the configured airport root.

        `settings.sharepoint_airport_root_folder` is a (possibly nested) path
        inside the drive whose children are the airport folders. Default is
        "RMP Master Directory/Airport - Safety Risk Management Documents".
        Graph path lookups are case-insensitive, so mixed-case folder names
        resolve correctly. When the setting is blank we list the drive root.
        """
        drives = await self.list_drives()
        configured_root = (settings.sharepoint_airport_root_folder or "").strip("/")
        folders: list[str] = []

        for drive in drives:
            if drive_name and drive.get("name", "").lower() != drive_name.lower():
                continue
            drive_id = drive["id"]

            url = _graph_path_url(drive_id, configured_root)

            try:
                count_before = len(folders)
                while url:
                    data = await self._graph_get(url)
                    for item in data.get("value", []):
                        if "folder" in item:
                            folders.append(item.get("name", ""))
                    url = data.get("@odata.nextLink", "")
                logger.info(
                    "sharepoint_airport_root_resolved",
                    drive=drive.get("name"),
                    configured_root=configured_root or "<drive root>",
                    airports_found=len(folders) - count_before,
                )
            except RuntimeError as exc:
                logger.warning(
                    "sharepoint_airport_root_unreadable",
                    drive=drive.get("name"),
                    configured_root=configured_root or "<drive root>",
                    error=str(exc),
                )
                continue

        return sorted({f for f in folders if f})

    async def list_risk_outcome_files(
        self, airport_identifier: str | None = None
    ) -> list[SharePointFile]:
        """Return every file under a Risk Outcome folder in the configured root.

        Tolerant folder-name match (spaces/dashes/underscores/case) handles
        variants like "Risk Outcome", "risk-outcome", "Risk_Outcome" etc.
        The airport identifier is resolved as the first path segment after
        `settings.sharepoint_airport_root_folder`, so files nested under
        projects or sub-projects still group under the right airport.

        Example paths that all resolve to airport "CLT":
            RMP Master Directory/Airport - Safety Risk Management Documents/CLT/
                CLT - 405-003-001 - Runway Decommission/Risk Outcome/x.pdf
            RMP Master Directory/Airport - Safety Risk Management Documents/CLT/
                CLT - 405-005 - Taxiway Nomenclature Change/Reports/Risk Outcome/y.pdf
        """
        all_files = await self.discover_files()
        matches: list[SharePointFile] = []
        airport_lc = airport_identifier.lower() if airport_identifier else None

        root_parts = [
            normalize_folder_name(s)
            for s in (settings.sharepoint_airport_root_folder or "").strip("/").split("/")
            if s
        ]

        # Track variants we actually see so a misnamed folder is visible in logs.
        folder_name_hits: set[str] = set()

        for f in all_files:
            segments = [s for s in f.folder_path.split("/") if s]
            # Must have a Risk Outcome folder somewhere in the chain.
            if not any(is_risk_outcome_folder(s) for s in segments):
                continue
            for s in segments:
                if is_risk_outcome_folder(s):
                    folder_name_hits.add(s)

            # Resolve the airport by locating the configured root prefix and
            # taking the segment that immediately follows it.
            file_airport: str | None = None
            if root_parts:
                normalized = [normalize_folder_name(s) for s in segments]
                for i in range(len(normalized) - len(root_parts) + 1):
                    if normalized[i : i + len(root_parts)] == root_parts:
                        ai = i + len(root_parts)
                        if ai < len(segments):
                            file_airport = segments[ai]
                        break
            elif segments:
                file_airport = segments[0]

            if airport_lc is not None and (
                file_airport is None or file_airport.lower() != airport_lc
            ):
                continue

            matches.append(f)

        logger.info(
            "sharepoint_risk_outcome_scanned",
            airport=airport_identifier,
            total_candidates=len(all_files),
            matched=len(matches),
            folder_name_variants_seen=list(folder_name_hits),
        )
        return matches

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
