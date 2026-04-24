from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExtractedSegment:
    """A unit of text from a source, with positional metadata for citations."""

    text: str
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    page: Optional[int] = None
    ts_start_ms: Optional[int] = None
    ts_end_ms: Optional[int] = None


@dataclass
class ExtractionResult:
    segments: list[ExtractedSegment]

    @property
    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.segments if s.text.strip())


def extract(path: Path, source_type: str) -> ExtractionResult:
    """Dispatch by source_type. Lazy imports keep startup fast and optional deps optional."""
    if source_type == "pdf":
        from .pdf import extract_pdf
        return extract_pdf(path)
    if source_type == "image":
        from .image import extract_image
        return extract_image(path)
    if source_type == "audio":
        from .audio import extract_audio
        return extract_audio(path)
    if source_type in ("text", "browser", "clipboard"):
        from .text import extract_text
        return extract_text(path)
    if source_type == "video":
        from .audio import extract_audio
        return extract_audio(path)
    return ExtractionResult(segments=[])
