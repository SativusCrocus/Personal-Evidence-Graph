from __future__ import annotations

import logging
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

# Make project siblings importable when running as `uvicorn app.main:app` from backend/
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]  # personal-evidence-graph/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.chunking import Chunk as ChunkData, chunk_segments  # noqa: E402
from ai.embeddings import embed  # noqa: E402
from ingestion.extractors import extract  # noqa: E402
from ingestion.extractors.clipboard import extract_clipboard_text  # noqa: E402
from ingestion.hashing import sha256_file  # noqa: E402
from ingestion.metadata import (  # noqa: E402
    best_source_dt,
    detect_mime,
    file_size,
    source_type_from_mime,
)

from ..config import Settings, get_settings
from ..deps import get_collection, session_scope
from ..models.db import Chunk, File
from ..security.paths import resolve_inside, safe_filename
from ..security.sanitize import sanitize_text

log = logging.getLogger("evg.ingestion")


def store_upload(tmp_bytes: bytes, original_name: str, settings: Optional[Settings] = None) -> Path:
    """Persist an uploaded byte stream into the uploads dir under a safe name."""
    s = settings or get_settings()
    s.ensure_dirs()
    name = safe_filename(original_name or "upload")
    target = s.upload_dir / f"{uuid.uuid4().hex[:8]}_{name}"
    target.write_bytes(tmp_bytes)
    return target


def find_duplicate(session: Session, sha: str) -> Optional[File]:
    return session.scalar(select(File).where(File.sha256 == sha))


def ingest_path(
    path: Path,
    *,
    settings: Optional[Settings] = None,
    move_to_uploads: bool = False,
) -> Tuple[str, bool]:
    """Index a single file end-to-end. Returns (file_id, was_duplicate)."""
    s = settings or get_settings()
    s.ensure_dirs()

    final_path = resolve_inside(s.allowed_roots, path)
    if not final_path.exists() or not final_path.is_file():
        raise FileNotFoundError(str(final_path))

    sha = sha256_file(final_path)
    with session_scope() as db:
        dup = find_duplicate(db, sha)
        if dup:
            return dup.id, True

    if move_to_uploads and final_path.parent != s.upload_dir:
        new = s.upload_dir / final_path.name
        shutil.copy2(final_path, new)
        final_path = new

    mime = detect_mime(final_path)
    stype = source_type_from_mime(mime, final_path)
    sdt = best_source_dt(final_path, mime)
    bytes_ = file_size(final_path)

    file_id = str(uuid.uuid4())
    with session_scope() as db:
        f = File(
            id=file_id,
            path=str(final_path),
            display_name=final_path.name,
            sha256=sha,
            mime=mime,
            bytes=bytes_,
            source_type=stype,
            ingested_at=datetime.now(timezone.utc),
            source_dt=sdt,
            status="extracting",
        )
        db.add(f)

    try:
        result = extract(final_path, stype)
        if not result.segments:
            _mark_status(file_id, "indexed", error=None)
            log.info("no extractable text from %s; recorded as empty", final_path)
            return file_id, False

        _persist_chunks_and_index(file_id, result.segments, s)
        _mark_status(file_id, "indexed")
        _maybe_extract_claims(file_id, s)
        return file_id, False
    except Exception as e:  # noqa: BLE001
        log.exception("ingest failed for %s", final_path)
        _mark_status(file_id, "failed", error=str(e)[:1000])
        raise


def ingest_clipboard(text: str, source_label: Optional[str] = None,
                     occurred_at: Optional[datetime] = None,
                     settings: Optional[Settings] = None) -> Tuple[str, bool]:
    """Ingest a text snippet (clipboard, browser selection, etc.)."""
    s = settings or get_settings()
    s.ensure_dirs()
    text = (text or "").strip()
    if not text:
        raise ValueError("empty clipboard text")

    payload = text.encode("utf-8")
    from ingestion.hashing import sha256_bytes
    sha = sha256_bytes(payload)

    with session_scope() as db:
        dup = find_duplicate(db, sha)
        if dup:
            return dup.id, True

    name = safe_filename((source_label or "clipboard")[:60]) + f"_{uuid.uuid4().hex[:6]}.txt"
    final_path = s.upload_dir / name
    final_path.write_bytes(payload)

    file_id = str(uuid.uuid4())
    with session_scope() as db:
        f = File(
            id=file_id,
            path=str(final_path),
            display_name=name,
            sha256=sha,
            mime="text/plain",
            bytes=len(payload),
            source_type="clipboard",
            ingested_at=datetime.now(timezone.utc),
            source_dt=occurred_at or datetime.now(timezone.utc),
            status="extracting",
        )
        db.add(f)

    res = extract_clipboard_text(text)
    _persist_chunks_and_index(file_id, res.segments, s)
    _mark_status(file_id, "indexed")
    _maybe_extract_claims(file_id, s)
    return file_id, False


def _persist_chunks_and_index(file_id: str, segments, settings: Settings) -> None:
    chunks: list[ChunkData] = chunk_segments(
        segments,
        max_tokens=settings.chunk_tokens,
        overlap_tokens=settings.chunk_overlap,
    )
    if not chunks:
        return

    chunk_rows: list[Chunk] = []
    for i, c in enumerate(chunks):
        text = sanitize_text(c.text, max_len=64_000)
        if not text.strip():
            continue
        chunk_rows.append(Chunk(
            id=str(uuid.uuid4()),
            file_id=file_id,
            ord=i,
            text=text,
            char_start=c.char_start,
            char_end=c.char_end,
            page=c.page,
            ts_start_ms=c.ts_start_ms,
            ts_end_ms=c.ts_end_ms,
            tokens=c.tokens,
        ))

    if not chunk_rows:
        return

    with session_scope() as db:
        for ch in chunk_rows:
            db.add(ch)

    vectors = embed([ch.text for ch in chunk_rows], settings.embed_model)
    coll = get_collection()

    with session_scope() as db:
        f = db.get(File, file_id)
        meta_template = {
            "file_id": file_id,
            "source_type": f.source_type if f else "other",
            "source_dt": (
                f.source_dt.isoformat() if f and f.source_dt else ""
            ),
        }

    metadatas = []
    for ch in chunk_rows:
        m = dict(meta_template)
        if ch.page is not None:
            m["page"] = ch.page
        if ch.ts_start_ms is not None:
            m["ts_start_ms"] = ch.ts_start_ms
        if ch.ts_end_ms is not None:
            m["ts_end_ms"] = ch.ts_end_ms
        metadatas.append(m)

    coll.upsert(
        ids=[ch.id for ch in chunk_rows],
        embeddings=vectors,
        documents=[ch.text for ch in chunk_rows],
        metadatas=metadatas,
    )


def _mark_status(file_id: str, status: str, error: Optional[str] = None) -> None:
    with session_scope() as db:
        f = db.get(File, file_id)
        if f:
            f.status = status
            f.error = error


def _maybe_extract_claims(file_id: str, settings: Settings) -> None:
    """Run the LLM claim extractor for a freshly-ingested file, then the
    obligation extractor on top of the claims that just landed. Never raises."""
    if settings.extract_claims_during_ingest:
        try:
            from .claim_extraction import extract_for_file_sync
            result = extract_for_file_sync(file_id, settings=settings)
            if result.claims_created or result.chunks_failed:
                log.info(
                    "claim extraction %s: %d claims, %d dropped, %d chunk failures (%dms)",
                    file_id, result.claims_created,
                    result.claims_dropped_invalid, result.chunks_failed,
                    result.elapsed_ms,
                )
        except Exception as e:  # noqa: BLE001
            log.warning("claim extraction step failed for %s: %s", file_id, e)

    if settings.extract_obligations_during_ingest:
        try:
            from .obligation_extraction import extract_for_file_sync as ob_extract
            ob_result = ob_extract(file_id, settings=settings)
            if ob_result.obligations_created or ob_result.claim_errors:
                log.info(
                    "obligation extraction %s: %d obligations, %d rejected, %d errors (%dms)",
                    file_id, ob_result.obligations_created,
                    ob_result.rejected_invalid, ob_result.claim_errors,
                    ob_result.elapsed_ms,
                )
        except Exception as e:  # noqa: BLE001
            log.warning("obligation extraction step failed for %s: %s", file_id, e)
