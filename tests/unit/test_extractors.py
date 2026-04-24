from __future__ import annotations

from pathlib import Path

from ingestion.extractors.text import extract_text


def test_text_extractor_reads_utf8(tmp_path: Path):
    p = tmp_path / "n.md"
    p.write_text("# Heading\n\nSome body text.", encoding="utf-8")
    res = extract_text(p)
    assert len(res.segments) == 1
    assert "Heading" in res.segments[0].text


def test_text_extractor_strips_html(tmp_path: Path):
    p = tmp_path / "n.html"
    p.write_text(
        "<html><body><script>alert(1)</script><h1>Title</h1><p>Hello world</p></body></html>",
        encoding="utf-8",
    )
    res = extract_text(p)
    body = res.segments[0].text
    assert "alert(1)" not in body
    assert "Title" in body
    assert "Hello world" in body


def test_text_extractor_falls_back_on_bad_encoding(tmp_path: Path):
    p = tmp_path / "n.txt"
    p.write_bytes(b"\xff\xfehello")  # not valid utf-8
    res = extract_text(p)
    assert "hello" in res.segments[0].text
