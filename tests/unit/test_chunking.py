from __future__ import annotations

from ai.chunking import chunk_text, chunk_segments
from ingestion.extractors import ExtractedSegment


def test_short_text_is_one_chunk():
    out = chunk_text("Short note.", max_tokens=512, overlap_tokens=0)
    assert len(out) == 1
    assert out[0].text == "Short note."
    assert out[0].char_start == 0
    assert out[0].char_end == len("Short note.")


def test_paragraph_chunking_respects_max_tokens():
    para = "This is a sentence. " * 200
    out = chunk_text(para, max_tokens=64, overlap_tokens=8)
    assert len(out) >= 5
    for c in out:
        assert c.tokens <= 64 + 16


def test_chunk_segments_preserves_page_metadata():
    segs = [
        ExtractedSegment(text="Page one body.", page=1, char_start=0, char_end=14),
        ExtractedSegment(text="Page two body.", page=2, char_start=20, char_end=34),
    ]
    out = chunk_segments(segs, max_tokens=512, overlap_tokens=0)
    pages = {c.page for c in out}
    assert pages == {1, 2}


def test_chunk_segments_preserves_audio_timestamps():
    segs = [
        ExtractedSegment(text="hello world transcript", ts_start_ms=1000, ts_end_ms=4000),
    ]
    out = chunk_segments(segs, max_tokens=512)
    assert all(c.ts_start_ms == 1000 and c.ts_end_ms == 4000 for c in out)


def test_empty_input_yields_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n   ") == []
