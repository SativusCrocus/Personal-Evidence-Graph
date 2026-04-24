from __future__ import annotations

from . import ExtractedSegment, ExtractionResult


def extract_clipboard_text(text: str) -> ExtractionResult:
    text = (text or "").strip()
    if not text:
        return ExtractionResult(segments=[])
    return ExtractionResult(
        segments=[ExtractedSegment(text=text, char_start=0, char_end=len(text))]
    )
