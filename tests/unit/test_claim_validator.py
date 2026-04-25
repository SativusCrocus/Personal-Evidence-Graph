"""Citation contract for claims: a claim's source_excerpt must verbatim
appear in its source chunk. Whitespace and case are normalized; nothing
else is. The validator is the gate for both ingest-time extraction and
audit-time replay.
"""
from __future__ import annotations

import pytest

from app.services.claims import excerpt_in_chunk, validate_claim


CHUNK = (
    "On April 8 2026 the Sequoia rep said: \"We'll have everything packed "
    "and out the door by April 15th.\" Owner replied: ok thanks."
)


def test_excerpt_must_be_present():
    assert excerpt_in_chunk(
        "We'll have everything packed and out the door by April 15th.",
        CHUNK,
    )


def test_normalizes_whitespace_and_case():
    excerpt = "  we'll have   EVERYTHING packed and out the door BY April 15th.  "
    assert excerpt_in_chunk(excerpt, CHUNK)


def test_rejects_paraphrase_not_present():
    assert not excerpt_in_chunk(
        "We will deliver everything by April 15.",
        CHUNK,
    )


def test_rejects_empty_excerpt():
    assert not excerpt_in_chunk("", CHUNK)
    assert not excerpt_in_chunk("anything", "")


def test_validate_claim_happy_path():
    ok, reason = validate_claim(
        "Delivery is promised by April 15.",
        "out the door by April 15th",
        CHUNK,
        confidence=0.9,
    )
    assert ok and reason is None


def test_validate_claim_rejects_blank_text():
    ok, reason = validate_claim(
        "   ",
        "out the door by April 15th",
        CHUNK,
        confidence=0.9,
    )
    assert not ok
    assert reason == "empty claim text"


def test_validate_claim_rejects_bad_confidence():
    ok, reason = validate_claim(
        "x", "out the door by April 15th", CHUNK, confidence=1.5,
    )
    assert not ok
    assert "confidence" in (reason or "")


def test_validate_claim_rejects_invented_excerpt():
    ok, reason = validate_claim(
        "Delivery promised by April 15.",
        "the rep guaranteed money-back if late",
        CHUNK,
        confidence=0.9,
    )
    assert not ok
    assert "verbatim" in (reason or "")


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan")])
def test_validate_claim_confidence_bounds(confidence: float):
    ok, _ = validate_claim("x", "out the door", CHUNK, confidence=confidence)
    assert not ok
