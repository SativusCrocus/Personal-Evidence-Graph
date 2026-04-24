from __future__ import annotations

from app.services import answer as answer_svc
from app.services.retrieval import RetrievedChunk


def _chunk(cid: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        file_id="file-1",
        file_name="n.txt",
        file_path="/tmp/n.txt",
        source_type="text",
        source_dt=None,
        text=text,
        page=None,
        ts_start_ms=None,
        ts_end_ms=None,
        score=0.9,
    )


def test_drops_invalid_chunk_id():
    parsed = {
        "answer": "yes",
        "citations": [{"chunk_id": "ghost", "excerpt": "approved the pricing"}],
        "confidence": 0.9,
    }
    chunks = {"a": _chunk("a", "On Jan 4 the client approved the pricing.")}
    answer, cites, _ = answer_svc._validate(parsed, chunks)
    assert cites == []
    assert answer == answer_svc.REFUSAL


def test_drops_excerpt_not_in_chunk():
    parsed = {
        "answer": "yes",
        "citations": [{"chunk_id": "a", "excerpt": "fabricated text not present"}],
        "confidence": 0.9,
    }
    chunks = {"a": _chunk("a", "On Jan 4 the client approved the pricing.")}
    answer, cites, _ = answer_svc._validate(parsed, chunks)
    assert cites == []
    assert answer == answer_svc.REFUSAL


def test_accepts_valid_substring_citation():
    parsed = {
        "answer": "Yes, on Jan 4 the client approved the pricing.",
        "citations": [{"chunk_id": "a", "excerpt": "approved the pricing"}],
        "confidence": 0.85,
    }
    chunks = {"a": _chunk("a", "On Jan 4 the client approved the pricing.")}
    answer, cites, conf = answer_svc._validate(parsed, chunks)
    assert len(cites) == 1
    assert cites[0].chunk_id == "a"
    assert "approved" in cites[0].excerpt
    assert conf == 0.85
    assert answer.startswith("Yes")


def test_excerpt_min_length_enforced():
    parsed = {
        "answer": "yes",
        "citations": [{"chunk_id": "a", "excerpt": "yes"}],
        "confidence": 0.9,
    }
    chunks = {"a": _chunk("a", "yes was the answer here.")}
    answer, cites, _ = answer_svc._validate(parsed, chunks)
    assert cites == []
    assert answer == answer_svc.REFUSAL


def test_explicit_refusal_passes_through():
    parsed = {
        "answer": "No supporting evidence found.",
        "citations": [],
        "confidence": 0.0,
    }
    answer, cites, conf = answer_svc._validate(parsed, {})
    assert answer == answer_svc.REFUSAL
    assert cites == []
    assert conf == 0.0


def test_extract_json_handles_prose_wrapper():
    parsed = answer_svc._extract_json(
        'Sure, here is your JSON: {"answer":"x","citations":[],"confidence":0.0} thanks'
    )
    assert parsed == {"answer": "x", "citations": [], "confidence": 0.0}


def test_extract_json_returns_none_on_garbage():
    assert answer_svc._extract_json("no json at all") is None
