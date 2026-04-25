"""Cross-encoder reranker for second-stage retrieval scoring.

The first stage (semantic + BM25 + RRF) is fast but noisy: BM25 over-weights
literal token matches and dense retrieval can pull semantically-adjacent but
off-topic chunks. A cross-encoder reads (query, candidate) pairs together
and produces a true relevance score. Slower per-pair, but only run on the
top-N candidates (default 20) so total query latency stays acceptable.

Loaded lazily on first use, cached by model name. Falls back to a no-op
identity rerank when sentence-transformers fails to import or load — the
caller still gets the original ranking.
"""
from __future__ import annotations

import logging
import threading
from typing import Sequence

log = logging.getLogger("evg.reranker")

_lock = threading.Lock()
_model = None
_model_name = ""


def _load(model_name: str):
    """Lazy-load CrossEncoder by name. Returns None if unavailable."""
    global _model, _model_name
    with _lock:
        if _model is not None and _model_name == model_name:
            return _model
        try:
            from sentence_transformers import CrossEncoder  # heavy import
            log.info("loading reranker model: %s", model_name)
            _model = CrossEncoder(model_name)
            _model_name = model_name
            return _model
        except Exception as e:  # noqa: BLE001
            log.warning("reranker load failed (%s); falling back to identity", e)
            _model = None
            _model_name = ""
            return None


def rerank(
    query: str,
    candidates: Sequence[str],
    *,
    model_name: str,
    top_k: int | None = None,
) -> list[tuple[int, float]]:
    """Score every (query, candidate) pair and return [(orig_index, score)]
    descending by score. If the model can't load, returns the original
    ordering with zeroed scores so callers can keep their first-stage rank.

    `top_k` truncates the returned list (the model still scores everything;
    the cost is per-pair, not per-result-returned).
    """
    if not candidates:
        return []

    model = _load(model_name)
    n = len(candidates)
    if model is None:
        # Identity fallback — preserve original ranking.
        return [(i, 0.0) for i in range(n)][: top_k or n]

    pairs = [(query, c) for c in candidates]
    try:
        raw_scores = model.predict(pairs, show_progress_bar=False)
    except Exception as e:  # noqa: BLE001
        log.warning("reranker predict failed (%s); identity fallback", e)
        return [(i, 0.0) for i in range(n)][: top_k or n]

    # Coerce scores to plain floats (predict returns numpy or list-of-numpy).
    scored = [(i, float(s)) for i, s in enumerate(raw_scores)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[: top_k or n]


def is_available(model_name: str) -> bool:
    """Probe whether the model can be loaded. Used by health endpoints."""
    return _load(model_name) is not None
