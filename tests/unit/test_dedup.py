from __future__ import annotations

from pathlib import Path

from ingestion.hashing import sha256_bytes, sha256_file


def test_sha256_stable(tmp_path: Path):
    p = tmp_path / "x.txt"
    p.write_bytes(b"abcdef")
    a = sha256_file(p)
    b = sha256_file(p)
    assert a == b
    assert a == sha256_bytes(b"abcdef")


def test_sha256_distinguishes(tmp_path: Path):
    a = tmp_path / "a.txt"; a.write_bytes(b"one")
    b = tmp_path / "b.txt"; b.write_bytes(b"two")
    assert sha256_file(a) != sha256_file(b)


def test_dedup_uses_sha_at_db_layer(sample_text_file: Path):
    """End-to-end: ingesting the same file twice yields duplicate=True the second time."""
    from app.services import ingestion

    file_id_1, dup_1 = ingestion.ingest_path(sample_text_file)
    file_id_2, dup_2 = ingestion.ingest_path(sample_text_file)
    assert dup_1 is False
    assert dup_2 is True
    assert file_id_1 == file_id_2
