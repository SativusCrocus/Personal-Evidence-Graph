"""Unit tests for the cross-encoder reranker.

The CrossEncoder model itself is mocked — we don't want to download an
80MB model in CI, and we want deterministic behavior for assertions.
Verifies:
  - empty input → empty output (no model load)
  - happy path: candidates re-ordered by mock scores
  - top_k truncates the result
  - identity fallback (zero scores) when model unavailable
  - predict() raising returns identity fallback, never propagates
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from ai import reranker as rr


def _reset_module_cache():
    """Reset the lazy-load cache between tests."""
    rr._model = None
    rr._model_name = ""


def test_rerank_empty_returns_empty_without_load():
    _reset_module_cache()
    with patch.object(rr, "_load") as fake_load:
        out = rr.rerank("anything", [], model_name="x")
        assert out == []
        fake_load.assert_not_called()


def test_rerank_reorders_by_model_scores():
    _reset_module_cache()
    fake_model = MagicMock()
    # Index 2 should rank first, then 0, then 1.
    fake_model.predict.return_value = [0.6, 0.1, 0.95]
    with patch.object(rr, "_load", return_value=fake_model):
        out = rr.rerank("q", ["a", "b", "c"], model_name="m")
    assert [idx for idx, _ in out] == [2, 0, 1]
    assert [round(s, 2) for _, s in out] == [0.95, 0.6, 0.1]


def test_rerank_top_k_truncates():
    _reset_module_cache()
    fake_model = MagicMock()
    fake_model.predict.return_value = [0.5, 0.4, 0.3, 0.2]
    with patch.object(rr, "_load", return_value=fake_model):
        out = rr.rerank("q", ["a", "b", "c", "d"], model_name="m", top_k=2)
    assert len(out) == 2
    assert [idx for idx, _ in out] == [0, 1]


def test_rerank_identity_fallback_when_model_unavailable():
    _reset_module_cache()
    with patch.object(rr, "_load", return_value=None):
        out = rr.rerank("q", ["a", "b", "c"], model_name="missing")
    # Identity: original order, zeroed scores.
    assert [idx for idx, _ in out] == [0, 1, 2]
    assert all(score == 0.0 for _, score in out)


def test_rerank_predict_failure_falls_back_to_identity():
    """Model loaded fine but predict() blows up — must not propagate."""
    _reset_module_cache()
    fake_model = MagicMock()
    fake_model.predict.side_effect = RuntimeError("OOM")
    with patch.object(rr, "_load", return_value=fake_model):
        out = rr.rerank("q", ["a", "b", "c"], model_name="m")
    assert [idx for idx, _ in out] == [0, 1, 2]
    assert all(score == 0.0 for _, score in out)


def test_load_caches_model_by_name():
    """A second call with the same name shouldn't re-import. Different name should."""
    _reset_module_cache()
    fake_a = MagicMock(name="model_a")
    fake_b = MagicMock(name="model_b")

    construct_calls = {"n": 0}

    class _FakeCrossEncoder:
        def __init__(self, name: str):
            construct_calls["n"] += 1
            self._name = name

    # Patch the CrossEncoder class via the import inside _load.
    import sys
    fake_module = MagicMock()
    fake_module.CrossEncoder = _FakeCrossEncoder
    sys.modules["sentence_transformers"] = fake_module
    try:
        m1 = rr._load("model-x")
        m2 = rr._load("model-x")
        assert m1 is m2
        assert construct_calls["n"] == 1
        m3 = rr._load("model-y")
        assert m3 is not m1
        assert construct_calls["n"] == 2
    finally:
        # Important: clean up the global cache so we don't leak the fake into
        # other tests that might import sentence_transformers for real.
        _reset_module_cache()
        sys.modules.pop("sentence_transformers", None)
        # Also unused refs
        del fake_a, fake_b
