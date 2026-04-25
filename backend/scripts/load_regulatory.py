"""
Bulk-load regulatory PDFs (FAA, ICAO, EASA, NASA ASRS) into the document pipeline.

Walks a folder structure where the immediate subdirectory name maps to a SourceType:

    regulatory/
      faa/        *.pdf
      icao/       *.pdf
      easa/       *.pdf
      nasa_asrs/  *.pdf | *.csv

Each file is uploaded via the existing /api/v1/documents/upload endpoint with the
matching source_type, then the backend's async pipeline chunks, embeds, and indexes
it into Azure AI Search.

Usage:
    cd backend && python -m scripts.load_regulatory \
        --root ../regulatory \
        --api https://ca-rmp-rmp-start-api.<region>.azurecontainerapps.io \
        --token "$ENTRA_BEARER_TOKEN" \
        --org-id <organization-uuid>

Notes:
  - Skips files whose filename already exists for the org (case-insensitive match).
  - Token must belong to a user with analyst or above in the target organization.
  - Run /api/v1/documents/stats/by-source after this finishes to verify counts.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

SOURCE_DIRS: dict[str, str] = {
    "faa": "faa",
    "icao": "icao",
    "easa": "easa",
    "nasa_asrs": "nasa_asrs",
    "client": "client",
}

ALLOWED_SUFFIXES = {".pdf", ".csv", ".txt", ".docx"}


async def _fetch_existing_filenames(client: httpx.AsyncClient, org_id: str) -> set[str]:
    resp = await client.get(
        "/api/v1/documents",
        params={"limit": 500},
        headers={"X-Organization-Id": org_id},
    )
    resp.raise_for_status()
    items = resp.json().get("data", [])
    return {item["filename"].lower() for item in items}


async def _upload_one(
    client: httpx.AsyncClient,
    file_path: Path,
    source_type: str,
    org_id: str,
) -> tuple[str, bool, str]:
    with file_path.open("rb") as fh:
        files = {"file": (file_path.name, fh, _content_type_for(file_path))}
        try:
            resp = await client.post(
                "/api/v1/documents/upload",
                params={"source_type": source_type},
                files=files,
                headers={"X-Organization-Id": org_id},
                timeout=300.0,
            )
        except httpx.HTTPError as exc:
            return file_path.name, False, f"HTTP error: {exc}"

    if resp.status_code >= 400:
        return file_path.name, False, f"{resp.status_code}: {resp.text[:200]}"
    return file_path.name, True, "ok"


def _content_type_for(file_path: Path) -> str:
    return {
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(file_path.suffix.lower(), "application/octet-stream")


async def _run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    headers = {"Authorization": f"Bearer {args.token}"}
    async with httpx.AsyncClient(base_url=args.api, headers=headers, timeout=120.0) as client:
        existing = await _fetch_existing_filenames(client, args.org_id) if not args.force else set()
        if existing:
            print(f"found {len(existing)} existing documents in org — will skip duplicates")

        plan: list[tuple[Path, str]] = []
        for subdir, source_type in SOURCE_DIRS.items():
            src_dir = root / subdir
            if not src_dir.is_dir():
                continue
            for path in sorted(src_dir.iterdir()):
                if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
                    continue
                if path.name.lower() in existing:
                    continue
                plan.append((path, source_type))

        if not plan:
            print("nothing to upload — all files already present, or directories empty")
            return 0

        print(f"uploading {len(plan)} files...")
        results: list[tuple[str, bool, str]] = []
        sem = asyncio.Semaphore(args.concurrency)

        async def _bound(path: Path, source_type: str) -> tuple[str, bool, str]:
            async with sem:
                result = await _upload_one(client, path, source_type, args.org_id)
                marker = "OK " if result[1] else "FAIL"
                print(f"  [{marker}] {source_type:10} {path.name} — {result[2]}")
                return result

        results = await asyncio.gather(*[_bound(p, st) for p, st in plan])

    ok = sum(1 for _, success, _ in results if success)
    print(f"\ndone: {ok} succeeded, {len(results) - ok} failed")
    print("verify with: GET /api/v1/documents/stats/by-source")
    return 0 if ok == len(results) else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Folder containing faa/, icao/, easa/, nasa_asrs/ subdirs")
    parser.add_argument("--api", required=True, help="Base URL of the Risk Manager Pro API")
    parser.add_argument("--token", required=True, help="Entra ID bearer token")
    parser.add_argument("--org-id", required=True, help="Target organization UUID")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel uploads (default: 3)")
    parser.add_argument("--force", action="store_true", help="Re-upload even if filename matches an existing doc")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(_run(_parse_args())))
