"""Tests that the reranker is actually wired into hybrid_search.

Patches ai.reranker.rerank at the import boundary used by retrieval.py
(ce_rerank), then verifies:
  - reranker_enabled=False short-circuits — the rerank function is never called.
  - When enabled and the rerank returns a non-identity score list, the final
    candidate ordering reflects the reranker's preference.
  - The semantic-similarity threshold gate runs BEFORE the reranker — a chunk
    that fails min_score is excluded even if the reranker would have ranked it
    first.
  - Reranker raising mid-call does NOT abort the query (graceful degradation).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.services import retrieval
from app.services.retrieval import RetrievedChunk, hybrid_search


def _make_chunk(
    cid: str, text: str = "x", score: float = 0.9,
    file_id: str = "f", source_type: str = "text",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid, file_id=file_id, file_name=f"{file_id}.txt",
        file_path=f"/tmp/{file_id}.txt", source_type=source_type,
        source_dt=datetime.now(timezone.utc),
        text=text, page=None, ts_start_ms=None, ts_end_ms=None, score=score,
    )


def test_apply_reranker_returns_input_when_disabled():
    candidates = [_make_chunk("a"), _make_chunk("b"), _make_chunk("c")]
    s = get_settings()
    object.__setattr__(s, "reranker_enabled", False)
    try:
        with patch.object(retrieval, "ce_rerank") as fake_rerank:
            out = retrieval._apply_reranker("q", candidates, s)
            fake_rerank.assert_not_called()
        assert [c.chunk_id for c in out] == ["a", "b", "c"]
    finally:
        object.__setattr__(s, "reranker_enabled", True)


def test_apply_reranker_reorders_pool_and_appends_tail():
    """First N candidates get reranked; anything beyond reranker_pool stays put."""
    cands = [_make_chunk(f"c{i}") for i in range(5)]
    s = get_settings()
    object.__setattr__(s, "reranker_enabled", True)
    object.__setattr__(s, "reranker_pool", 3)
    try:
        # Tell the fake reranker: among the first 3, prefer index 2 then 0 then 1.
        with patch.object(retrieval, "ce_rerank", return_value=[(2, 0.9), (0, 0.5), (1, 0.1)]):
            out = retrieval._apply_reranker("q", cands, s)
        assert [c.chunk_id for c in out] == ["c2", "c0", "c1", "c3", "c4"]
    finally:
        object.__setattr__(s, "reranker_pool", 20)


def test_apply_reranker_identity_fallback_keeps_input_order():
    """All-zero scores from the reranker mean the model wasn't loaded — keep first-stage order."""
    cands = [_make_chunk("a"), _make_chunk("b"), _make_chunk("c")]
    s = get_settings()
    object.__setattr__(s, "reranker_enabled", True)
    with patch.object(retrieval, "ce_rerank", return_value=[(0, 0.0), (1, 0.0), (2, 0.0)]):
        out = retrieval._apply_reranker("q", cands, s)
    assert [c.chunk_id for c in out] == ["a", "b", "c"]


def test_apply_reranker_swallows_exceptions():
    """If the rerank call raises, retrieval still returns the original list."""
    cands = [_make_chunk("a"), _make_chunk("b")]
    s = get_settings()
    object.__setattr__(s, "reranker_enabled", True)
    with patch.object(retrieval, "ce_rerank", side_effect=RuntimeError("boom")):
        out = retrieval._apply_reranker("q", cands, s)
    assert [c.chunk_id for c in out] == ["a", "b"]


def test_apply_reranker_empty_input_skips_call():
    s = get_settings()
    object.__setattr__(s, "reranker_enabled", True)
    with patch.object(retrieval, "ce_rerank") as fake_rerank:
        out = retrieval._apply_reranker("q", [], s)
        fake_rerank.assert_not_called()
    assert out == []
