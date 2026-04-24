from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

_PARA = re.compile(r"\n\s*\n+")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass
class Chunk:
    text: str
    char_start: int
    char_end: int
    page: int | None = None
    ts_start_ms: int | None = None
    ts_end_ms: int | None = None
    tokens: int = 0


def _approx_tokens(s: str) -> int:
    """Cheap token estimator: ~4 chars/token. Good enough for chunk sizing."""
    return max(1, (len(s) + 3) // 4)


def chunk_text(
    text: str,
    *,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
    page: int | None = None,
    char_offset: int = 0,
) -> list[Chunk]:
    """Recursive structural chunker: paragraph → sentence → hard slice.

    Greedy pack to `max_tokens`; if a single unit exceeds the budget, split it
    further. Overlap is character-based (token-approximated) appended to each
    boundary so context doesn't break across chunks.
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = [p for p in _PARA.split(text) if p.strip()]
    units: list[str] = []
    for p in paragraphs:
        if _approx_tokens(p) <= max_tokens:
            units.append(p)
        else:
            for sent in _SENT.split(p):
                if not sent.strip():
                    continue
                if _approx_tokens(sent) <= max_tokens:
                    units.append(sent)
                else:
                    units.extend(_hard_slice(sent, max_tokens))

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_tokens = 0
    cursor = 0

    overlap_chars = overlap_tokens * 4

    def _flush() -> None:
        nonlocal buf, buf_tokens, cursor
        if not buf:
            return
        body = "\n\n".join(buf).strip()
        if not body:
            buf = []
            buf_tokens = 0
            return
        try:
            start = text.index(body, cursor)
        except ValueError:
            start = cursor
        end = start + len(body)
        chunks.append(Chunk(
            text=body,
            char_start=char_offset + start,
            char_end=char_offset + end,
            page=page,
            tokens=_approx_tokens(body),
        ))
        cursor = max(0, end - overlap_chars)
        buf = []
        buf_tokens = 0

    for unit in units:
        ut = _approx_tokens(unit)
        if buf_tokens + ut > max_tokens and buf:
            _flush()
        buf.append(unit)
        buf_tokens += ut
    _flush()

    return chunks


def _hard_slice(s: str, max_tokens: int) -> list[str]:
    max_chars = max_tokens * 4
    return [s[i : i + max_chars] for i in range(0, len(s), max_chars)]


def chunk_segments(
    segments: Iterable,
    *,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
) -> list[Chunk]:
    """Chunk a sequence of ExtractedSegment, preserving page/timestamp metadata."""
    out: list[Chunk] = []
    for seg in segments:
        sub = chunk_text(
            seg.text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            page=getattr(seg, "page", None),
            char_offset=int(getattr(seg, "char_start", 0) or 0),
        )
        ts_start = getattr(seg, "ts_start_ms", None)
        ts_end = getattr(seg, "ts_end_ms", None)
        if ts_start is not None or ts_end is not None:
            for c in sub:
                c.ts_start_ms = ts_start
                c.ts_end_ms = ts_end
        out.extend(sub)
    return out
