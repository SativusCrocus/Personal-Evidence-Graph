from __future__ import annotations

from pathlib import Path

from . import ExtractedSegment, ExtractionResult


def extract_browser_export(path: Path) -> ExtractionResult:
    """Treat HTML/JSON exports as text; downstream chunker handles rest."""
    from .text import extract_text
    return extract_text(path)


__all__ = ["extract_browser_export"]
