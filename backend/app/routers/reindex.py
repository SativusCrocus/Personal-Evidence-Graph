from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select

from ..config import Settings
from ..deps import get_collection, session_scope, settings_dep
from ..models.db import Chunk, File

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.embeddings import embed  # noqa: E402

log = logging.getLogger("evg.router.reindex")
router = APIRouter(tags=["admin"])


@router.post("/reindex")
def reindex(background: BackgroundTasks, s: Settings = Depends(settings_dep)) -> dict:
    background.add_task(_reindex_all, s)
    return {"queued": True}


def _reindex_all(s: Settings) -> None:
    log.info("reindex starting")
    coll = get_collection()
    try:
        coll.delete(where={})
    except Exception as e:  # noqa: BLE001
        log.debug("chroma clear (delete-all) failed (continuing): %s", e)

    BATCH = 256
    with session_scope() as db:
        total = db.query(Chunk).count()
    if total == 0:
        log.info("reindex: no chunks")
        return

    offset = 0
    indexed = 0
    while offset < total:
        with session_scope() as db:
            rows = (
                db.query(Chunk, File)
                .join(File, File.id == Chunk.file_id)
                .order_by(Chunk.id.asc())
                .limit(BATCH)
                .offset(offset)
                .all()
            )
        if not rows:
            break
        ids = [r[0].id for r in rows]
        texts = [r[0].text for r in rows]
        metas = []
        for ch, f in rows:
            m = {
                "file_id": f.id,
                "source_type": f.source_type,
                "source_dt": f.source_dt.isoformat() if f.source_dt else "",
            }
            if ch.page is not None:
                m["page"] = ch.page
            if ch.ts_start_ms is not None:
                m["ts_start_ms"] = ch.ts_start_ms
            if ch.ts_end_ms is not None:
                m["ts_end_ms"] = ch.ts_end_ms
            metas.append(m)
        vectors = embed(texts, s.embed_model)
        coll.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metas)
        indexed += len(rows)
        offset += BATCH
        log.info("reindex progress: %d/%d", indexed, total)
    log.info("reindex done: %d chunks", indexed)
