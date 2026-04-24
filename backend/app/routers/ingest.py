from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File as FFile, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_session, settings_dep
from ..models.db import File
from ..models.schemas import (
    IngestClipboardRequest,
    IngestFolderRequest,
    IngestResponse,
)
from ..security import limiter
from ..security.paths import PathSafetyError, resolve_inside, safe_filename
from ..services import ingestion
from ..services.enrichment import enrich_file

log = logging.getLogger("evg.router.ingest")
router = APIRouter(prefix="/ingest", tags=["ingest"])


def _enqueue_enrichment(bg: BackgroundTasks, file_id: str) -> None:
    bg.add_task(_run_enrichment, file_id)


async def _run_enrichment(file_id: str) -> None:
    try:
        await enrich_file(file_id)
    except Exception as e:  # noqa: BLE001
        log.warning("background enrichment failed for %s: %s", file_id, e)


@router.post("/file", response_model=IngestResponse)
@limiter.limit("60/minute")
async def ingest_file(
    request: Request,
    background: BackgroundTasks,
    upload: UploadFile = FFile(...),
    s: Settings = Depends(settings_dep),
) -> IngestResponse:
    max_bytes = s.max_upload_mb * 1024 * 1024
    body = await upload.read()
    if len(body) > max_bytes:
        raise HTTPException(status_code=413, detail=f"file exceeds {s.max_upload_mb}MB")
    if not body:
        raise HTTPException(status_code=400, detail="empty upload")

    name = safe_filename(upload.filename or "upload")
    target = ingestion.store_upload(body, name, settings=s)

    try:
        file_id, dup = await asyncio.to_thread(
            ingestion.ingest_path, target, settings=s,
        )
    except PathSafetyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ingest failed: {e}") from e

    if not dup:
        _enqueue_enrichment(background, file_id)

    sha = await asyncio.to_thread(_get_sha, file_id)
    return IngestResponse(file_id=file_id, sha256=sha or "", status="indexed", duplicate=dup)


@router.post("/folder", response_model=list[IngestResponse])
@limiter.limit("10/minute")
async def ingest_folder(
    request: Request,
    body: IngestFolderRequest,
    background: BackgroundTasks,
    s: Settings = Depends(settings_dep),
) -> list[IngestResponse]:
    try:
        root = resolve_inside(s.allowed_roots, body.path)
    except PathSafetyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="path is not a directory")

    iterator = root.rglob("*") if body.recursive else root.glob("*")
    results: list[IngestResponse] = []
    for p in iterator:
        if not p.is_file():
            continue
        try:
            file_id, dup = await asyncio.to_thread(ingestion.ingest_path, p, settings=s)
            if not dup:
                _enqueue_enrichment(background, file_id)
            sha = await asyncio.to_thread(_get_sha, file_id)
            results.append(IngestResponse(
                file_id=file_id, sha256=sha or "", status="indexed", duplicate=dup
            ))
        except Exception as e:  # noqa: BLE001
            log.warning("skipping %s: %s", p, e)
    return results


@router.post("/clipboard", response_model=IngestResponse)
@limiter.limit("60/minute")
async def ingest_clipboard(
    request: Request,
    body: IngestClipboardRequest,
    background: BackgroundTasks,
    s: Settings = Depends(settings_dep),
) -> IngestResponse:
    try:
        file_id, dup = await asyncio.to_thread(
            ingestion.ingest_clipboard,
            body.text, body.source, body.occurred_at, s,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not dup:
        _enqueue_enrichment(background, file_id)
    sha = await asyncio.to_thread(_get_sha, file_id)
    return IngestResponse(file_id=file_id, sha256=sha or "", status="indexed", duplicate=dup)


def _get_sha(file_id: str) -> str | None:
    from ..deps import session_scope
    with session_scope() as db:
        f = db.get(File, file_id)
        return f.sha256 if f else None
