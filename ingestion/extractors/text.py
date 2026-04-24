from __future__ import annotations

from pathlib import Path

from . import ExtractedSegment, ExtractionResult


def extract_text(path: Path) -> ExtractionResult:
    raw = _read_with_fallback(path)
    if path.suffix.lower() in {".html", ".htm", ".mhtml"}:
        raw = _strip_html(raw)
    return ExtractionResult(segments=[ExtractedSegment(text=raw, char_start=0, char_end=len(raw))])


def _read_with_fallback(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    try:
        from html.parser import HTMLParser

        class _S(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
                self.skip = 0

            def handle_starttag(self, tag: str, attrs):  # type: ignore[no-untyped-def]
                if tag in {"script", "style", "noscript"}:
                    self.skip += 1

            def handle_endtag(self, tag: str) -> None:
                if tag in {"script", "style", "noscript"} and self.skip:
                    self.skip -= 1

            def handle_data(self, data: str) -> None:
                if not self.skip:
                    self.parts.append(data)

        p = _S()
        p.feed(html)
        return " ".join(" ".join(p.parts).split())
    except Exception:  # noqa: BLE001
        return html
