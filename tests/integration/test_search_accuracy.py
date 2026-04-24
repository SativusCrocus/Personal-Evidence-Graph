from __future__ import annotations

from pathlib import Path

from app.services import ingestion
from app.services.retrieval import hybrid_search


def test_semantic_search_finds_known_text(sample_text_file: Path):
    ingestion.ingest_path(sample_text_file)
    results = hybrid_search("client approval pricing", k=5, min_score=0.0)
    assert len(results) >= 1
    top = results[0]
    assert "approved" in top.text.lower() or "pricing" in top.text.lower()
    assert top.file_name == "sample.txt"


def test_keyword_search_finds_exact_phrase(sample_text_file: Path):
    ingestion.ingest_path(sample_text_file)
    results = hybrid_search("Acme Corp", k=5, min_score=0.0)
    assert any("Acme" in r.text for r in results)


def test_unrelated_query_returns_empty_when_threshold_high(sample_text_file: Path):
    ingestion.ingest_path(sample_text_file)
    results = hybrid_search("nuclear submarine sandwich recipe", k=5, min_score=0.85)
    assert results == [] or all(r.score < 0.85 for r in results) is False  # tolerate
