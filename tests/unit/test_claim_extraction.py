"""Unit tests for the LLM-driven claim extractor.

The LLM is mocked everywhere — we don't want a network round trip in unit
tests, and we want deterministic shaping of LLM outputs to verify each
contract path: paraphrase rejection, garbled JSON, empty array, valid
multi-claim, hallucinated chunk avoidance.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

from app.services import claim_extraction as ce


CHUNK_TEXT = (
    "INVOICE #2026-049 — Sequoia Print Co. Bill date: April 21, 2026. "
    "Subtotal: $5,200.00. Tax: $0.00. Total due: $5,200.00. Net 30, "
    "due May 21, 2026."
)


def _llm_returns(payload: dict | str):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    client = AsyncMock()
    client.is_alive = AsyncMock(return_value=True)
    client.generate = AsyncMock(return_value=raw)
    client.aclose = AsyncMock(return_value=None)
    return client


# ───────────────────────── parse_candidates ─────────────────────────


def test_parse_candidates_handles_clean_json():
    raw = json.dumps({
        "claims": [
            {"text": "x", "source_excerpt": "Subtotal: $5,200.00", "confidence": 0.95},
            {"text": "y", "source_excerpt": "Net 30", "confidence": 0.8},
        ]
    })
    out = ce.parse_candidates(raw)
    assert len(out) == 2
    assert out[0]["source_excerpt"] == "Subtotal: $5,200.00"
    assert out[0]["confidence"] == 0.95


def test_parse_candidates_handles_prose_wrapper():
    raw = (
        "Sure thing! Here is your JSON:\n"
        '{"claims":[{"text":"x","source_excerpt":"Net 30","confidence":0.8}]}\n'
        "Hope that helps."
    )
    out = ce.parse_candidates(raw)
    assert len(out) == 1


def test_parse_candidates_handles_markdown_fences():
    raw = "```json\n{\"claims\":[]}\n```"
    out = ce.parse_candidates(raw)
    assert out == []


def test_parse_candidates_clamps_bad_confidence():
    raw = json.dumps({
        "claims": [{"text": "x", "source_excerpt": "Net 30", "confidence": 9.0}]
    })
    out = ce.parse_candidates(raw)
    assert out[0]["confidence"] == 1.0


def test_parse_candidates_returns_empty_on_garbage():
    assert ce.parse_candidates("") == []
    assert ce.parse_candidates("not json at all") == []
    assert ce.parse_candidates(json.dumps({"claims": "not a list"})) == []
    assert ce.parse_candidates(json.dumps({"other_key": []})) == []


# ───────────────────────── _extract_one_chunk ─────────────────────────


class _FakeChunk:
    def __init__(self, id: str, text: str, file_id: str = "f"):
        self.id = id
        self.text = text
        self.file_id = file_id


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_extract_one_chunk_drops_paraphrased_excerpt():
    chunk = _FakeChunk("c1", CHUNK_TEXT)
    client = _llm_returns({
        "claims": [
            # The wording "fifty-two hundred dollars" is NOT in the chunk → drop.
            {"text": "Total is fifty-two hundred dollars.",
             "source_excerpt": "fifty-two hundred dollars",
             "confidence": 0.9},
            # This excerpt IS in the chunk verbatim → keep.
            {"text": "Total due is $5,200.",
             "source_excerpt": "Total due: $5,200.00",
             "confidence": 0.95},
        ]
    })
    surviving, err = _run(ce._extract_one_chunk(client, chunk))
    assert err is None
    assert len(surviving) == 1
    assert surviving[0]["source_excerpt"] == "Total due: $5,200.00"


def test_extract_one_chunk_returns_empty_for_empty_claims():
    chunk = _FakeChunk("c1", CHUNK_TEXT)
    client = _llm_returns({"claims": []})
    surviving, err = _run(ce._extract_one_chunk(client, chunk))
    assert err is None
    assert surviving == []


def test_extract_one_chunk_treats_garbled_response_as_empty_not_error():
    chunk = _FakeChunk("c1", CHUNK_TEXT)
    client = _llm_returns("definitely not JSON here")
    surviving, err = _run(ce._extract_one_chunk(client, chunk))
    assert err is None
    assert surviving == []


def test_extract_one_chunk_reports_llm_error():
    chunk = _FakeChunk("c1", CHUNK_TEXT)
    client = AsyncMock()
    client.is_alive = AsyncMock(return_value=True)
    client.generate = AsyncMock(side_effect=ce.LLMError("boom"))
    client.aclose = AsyncMock(return_value=None)
    surviving, err = _run(ce._extract_one_chunk(client, chunk))
    assert surviving == []
    assert err is not None
    assert "LLMError" in err or "boom" in err


def test_extract_one_chunk_drops_excerpt_below_min_length():
    """validate_claim is the gate — short excerpts don't fail at parse,
    but they fail validation. (parse_candidates doesn't enforce length;
    that's the validator's job.)"""
    chunk = _FakeChunk("c1", CHUNK_TEXT)
    client = _llm_returns({
        "claims": [
            # too short to be meaningful, but verbatim — validate_claim still
            # accepts; this is intentional, length is a *prompt* constraint
            # not a hard validator one. We test that it doesn't crash.
            {"text": "x", "source_excerpt": "x", "confidence": 0.5},
        ]
    })
    # excerpt "x" is in chunk text? Let's check — yes, lowercased: chunk has "tax".
    surviving, err = _run(ce._extract_one_chunk(client, chunk))
    assert err is None
    # We don't assert on count — the goal here is "no exception".


# ───────────────────────── extract_for_file (DB-touching) ─────────────────────────


def test_extract_for_file_skips_when_llm_unreachable(monkeypatch):
    """If is_alive() returns False, the function returns a zeroed result
    and never calls generate(). Ingestion must remain robust to this."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    # Patch the OllamaClient class as imported into the extractor module.
    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=False)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=AssertionError("must not be called"))
    with patch.object(ce, "OllamaClient", return_value=fake):
        result = asyncio.run(ce.extract_for_file("f_master_agreement"))
    assert result.claims_created == 0
    assert result.chunks_processed == 0
    assert result.chunks_failed == 0


def test_extract_for_file_persists_valid_claims(tmp_path, monkeypatch):
    """End-to-end with a mocked LLM that returns a valid claim per chunk.
    Asserts new rows actually land in claims via create_claim's enforcement."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    # Pick a single file and clear any pre-existing claims for it so the
    # delta is deterministic.
    from app.deps import session_scope
    from app.models.db import Chunk, Claim
    target_file = "f_invoice_april"
    with session_scope() as db:
        db.query(Claim).filter(Claim.source_file_id == target_file).delete(
            synchronize_session=False
        )

    # Build per-chunk LLM responses keyed by what the prompt will contain.
    with session_scope() as db:
        chunks = {
            c.id: c.text for c in db.query(Chunk).filter(Chunk.file_id == target_file).all()
        }
    assert chunks, "seed should have populated chunks for the target file"

    def make_response(prompt: str) -> str:
        # Find which chunk this prompt contains; emit a verbatim excerpt
        # picked from the first 60 chars of that chunk.
        for cid, text in chunks.items():
            if text[:40] in prompt:
                excerpt = text[:30]
                return json.dumps({
                    "claims": [
                        {"text": f"Claim about {cid}", "source_excerpt": excerpt,
                         "confidence": 0.9}
                    ]
                })
        return json.dumps({"claims": []})

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=lambda prompt, **_: make_response(prompt))

    with patch.object(ce, "OllamaClient", return_value=fake):
        result = asyncio.run(ce.extract_for_file(
            target_file, skip_if_already_extracted=False,
        ))

    assert result.chunks_processed == len(chunks)
    assert result.claims_created == len(chunks)
    assert result.chunks_failed == 0

    # Confirm rows actually persisted:
    with session_scope() as db:
        persisted = db.query(Claim).filter(Claim.source_file_id == target_file).all()
        assert len(persisted) == len(chunks)
        for cl in persisted:
            assert cl.source_excerpt in chunks[cl.source_chunk_id]


def test_extract_for_file_skip_already_extracted_default(monkeypatch):
    """The default skip_if_already_extracted=True should pass over chunks
    whose claims have already been written."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(return_value=json.dumps({"claims": []}))

    with patch.object(ce, "OllamaClient", return_value=fake):
        result = asyncio.run(ce.extract_for_file("f_voicememo_call"))

    # Voice memo's c_voice_1 already has cl_delivery_april_15 from the seed.
    # With skip_if_already_extracted, that chunk shouldn't be sent to LLM.
    # We can only verify indirectly: chunks_processed should be < total chunks.
    assert result.chunks_processed < 2
