from __future__ import annotations

import re

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_text(s: str, max_len: int = 4_000_000) -> str:
    """Strip control bytes; cap length. Used on extracted text before persistence."""
    if s is None:
        return ""
    s = _CONTROL.sub("", s)
    if len(s) > max_len:
        s = s[:max_len]
    return s


def sanitize_question(q: str, max_len: int = 4000) -> str:
    """Normalize a user question. Trim, drop control chars, cap length."""
    q = (q or "").strip()
    q = _CONTROL.sub(" ", q)
    q = re.sub(r"\s+", " ", q)
    if len(q) > max_len:
        q = q[:max_len]
    return q
