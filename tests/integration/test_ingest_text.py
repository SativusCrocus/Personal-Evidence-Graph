from __future__ import annotations

from pathlib import Path

from app.deps import session_scope
from app.models.db import Chunk, File
from app.services import ingestion


def test_ingest_text_file_creates_indexed_record(sample_text_file: Path):
    file_id, dup = ingestion.ingest_path(sample_text_file)
    assert dup is False
    with session_scope() as db:
        f = db.get(File, file_id)
        assert f is not None
        assert f.status == "indexed"
        assert f.source_type == "text"
        assert f.bytes > 0
        chunks = db.query(Chunk).filter(Chunk.file_id == file_id).all()
        assert len(chunks) >= 1
        assert any("approved the pricing" in c.text for c in chunks)


def test_ingest_clipboard_creates_record():
    file_id, dup = ingestion.ingest_clipboard(
        "Quick note: invoice #1042 is overdue as of 2025-02-14.",
        source_label="email-snippet",
    )
    assert dup is False
    with session_scope() as db:
        f = db.get(File, file_id)
        assert f is not None
        assert f.source_type == "clipboard"
        assert f.status == "indexed"


def test_chroma_chunks_match_sqlite(sample_text_file: Path):
    file_id, _ = ingestion.ingest_path(sample_text_file)
    from app.deps import get_collection

    coll = get_collection()
    with session_scope() as db:
        ids = [c.id for c in db.query(Chunk).filter(Chunk.file_id == file_id).all()]
    if not ids:
        return
    got = coll.get(ids=ids)
    assert set(got.get("ids") or []) == set(ids)
