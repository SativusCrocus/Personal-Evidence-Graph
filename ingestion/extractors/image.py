from __future__ import annotations

import logging
from pathlib import Path

from . import ExtractedSegment, ExtractionResult

log = logging.getLogger("evg.extractor.image")


def extract_image(path: Path) -> ExtractionResult:
    text = _ocr(path)
    text = text.strip()
    if not text:
        return ExtractionResult(segments=[])
    return ExtractionResult(
        segments=[ExtractedSegment(text=text, char_start=0, char_end=len(text))]
    )


def _ocr(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except Exception as e:  # noqa: BLE001
        log.warning("OCR deps unavailable: %s", e)
        return ""
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            return pytesseract.image_to_string(img) or ""
    except Exception as e:  # noqa: BLE001
        log.warning("OCR failed for %s: %s", path, e)
        return ""
