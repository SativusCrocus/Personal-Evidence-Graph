from __future__ import annotations

import logging
from pathlib import Path

from . import ExtractedSegment, ExtractionResult

log = logging.getLogger("evg.extractor.pdf")
_MIN_TEXT_PER_PAGE = 30


def extract_pdf(path: Path) -> ExtractionResult:
    """Extract per-page text via pypdfium2; OCR fallback for image-only pages."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    segments: list[ExtractedSegment] = []
    cursor = 0
    try:
        for page_idx in range(len(pdf)):
            page = pdf[page_idx]
            text = ""
            try:
                tp = page.get_textpage()
                text = tp.get_text_range() or ""
                tp.close()
            except Exception as e:  # noqa: BLE001
                log.debug("pdfium text extract failed page=%d: %s", page_idx, e)

            if len(text.strip()) < _MIN_TEXT_PER_PAGE:
                ocr = _ocr_page(page)
                if len(ocr.strip()) > len(text.strip()):
                    text = ocr

            text = text.strip()
            if text:
                seg = ExtractedSegment(
                    text=text,
                    char_start=cursor,
                    char_end=cursor + len(text),
                    page=page_idx + 1,
                )
                segments.append(seg)
                cursor += len(text) + 2
            page.close()
    finally:
        pdf.close()

    return ExtractionResult(segments=segments)


def _ocr_page(page) -> str:  # type: ignore[no-untyped-def]
    try:
        import pytesseract
        from PIL import Image  # noqa: F401  (Pillow used by pdfium render)
    except Exception:  # noqa: BLE001
        return ""
    try:
        bitmap = page.render(scale=2.0).to_pil()
        return pytesseract.image_to_string(bitmap) or ""
    except Exception as e:  # noqa: BLE001
        log.debug("pdf ocr fallback failed: %s", e)
        return ""
