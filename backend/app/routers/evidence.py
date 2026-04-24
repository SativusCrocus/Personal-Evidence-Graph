from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_session, settings_dep
from ..models.db import Chunk, Enrichment, File
from ..models.schemas import ChunkOut, EvidenceDetail, FileSummary
from ..security.paths import PathSafetyError, resolve_inside

log = logging.getLogger("evg.router.evidence")
router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/{chunk_id}", response_model=EvidenceDetail)
def get_evidence(
    chunk_id: str,
    db: Session = Depends(get_session),
) -> EvidenceDetail:
    ch = db.get(Chunk, chunk_id)
    if not ch:
        raise HTTPException(status_code=404, detail="chunk not found")
    f = db.get(File, ch.file_id)
    if not f:
        raise HTTPException(status_code=404, detail="orphan chunk")

    neighbors = (
        db.query(Chunk)
        .filter(Chunk.file_id == f.id)
        .filter(Chunk.ord.between(max(0, ch.ord - 2), ch.ord + 2))
        .filter(Chunk.id != ch.id)
        .order_by(Chunk.ord.asc())
        .all()
    )

    enrich_rows = (
        db.query(Enrichment)
        .filter((Enrichment.chunk_id == ch.id) | (Enrichment.file_id == f.id))
        .all()
    )
    enrich_payload = [
        {"kind": e.kind, "value": _safe_json(e.value), "confidence": e.confidence}
        for e in enrich_rows
    ]

    chunk_count = db.query(Chunk).filter(Chunk.file_id == f.id).count()

    return EvidenceDetail(
        chunk=ChunkOut(
            id=ch.id, ord=ch.ord, text=ch.text,
            page=ch.page, ts_start_ms=ch.ts_start_ms, ts_end_ms=ch.ts_end_ms,
        ),
        file=FileSummary(
            id=f.id, display_name=f.display_name, path=f.path,
            source_type=f.source_type, status=f.status, bytes=f.bytes,
            ingested_at=f.ingested_at, source_dt=f.source_dt,
            chunk_count=chunk_count,
        ),
        neighbors=[
            ChunkOut(
                id=n.id, ord=n.ord, text=n.text,
                page=n.page, ts_start_ms=n.ts_start_ms, ts_end_ms=n.ts_end_ms,
            ) for n in neighbors
        ],
        enrichments=enrich_payload,
    )


@router.get("/file/{file_id}/raw")
def get_raw_file(
    file_id: str,
    db: Session = Depends(get_session),
    s: Settings = Depends(settings_dep),
):
    f = db.get(File, file_id)
    if not f:
        raise HTTPException(status_code=404, detail="file not found")
    try:
        path = resolve_inside(s.allowed_roots, f.path)
    except PathSafetyError:
        raise HTTPException(status_code=403, detail="file path not in allowed roots")
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing on disk")
    media_type = f.mime or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return FileResponse(str(path), media_type=media_type, filename=f.display_name)


def _safe_json(s: str):
    try:
        return json.loads(s)
    except Exception:  # noqa: BLE001
        return {"raw": s}
