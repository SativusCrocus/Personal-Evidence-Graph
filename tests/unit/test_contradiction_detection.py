"""Unit tests for the cross-claim contradiction detector.

Mocks both the LLM and the embedding function — no network, no
sentence-transformers load. Verifies:
  - parse_judgment shape handling
  - top_k_candidates K-NN math (deterministic vectors)
  - silent skip when LLM is_alive=False
  - end-to-end persist + back-link both claims
  - dedup: re-running over the same pair doesn't create a duplicate
  - same-chunk pairs are skipped (consistent by construction)
  - pair errors are isolated, not propagated
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from app.services import contradiction_detection as cd


# ───────────────────────── parse_judgment ─────────────────────────


def test_parse_judgment_clean_positive():
    raw = json.dumps({
        "is_contradiction": True,
        "topic": "Monthly invoice total",
        "severity": "high",
        "summary": "March was $4,500; April is $5,200 with no notice.",
    })
    out = cd.parse_judgment(raw)
    assert out is not None
    assert out["topic"] == "Monthly invoice total"
    assert out["severity"] == "high"


def test_parse_judgment_negative_returns_none():
    assert cd.parse_judgment(json.dumps({"is_contradiction": False})) is None


def test_parse_judgment_missing_required_returns_none():
    assert cd.parse_judgment(json.dumps({
        "is_contradiction": True, "summary": "x"
        # no topic
    })) is None
    assert cd.parse_judgment(json.dumps({
        "is_contradiction": True, "topic": "x"
        # no summary
    })) is None


def test_parse_judgment_clamps_unknown_severity_to_medium():
    raw = json.dumps({
        "is_contradiction": True, "topic": "x", "summary": "y", "severity": "catastrophic",
    })
    out = cd.parse_judgment(raw)
    assert out is not None
    assert out["severity"] == "medium"


def test_parse_judgment_handles_garbage():
    assert cd.parse_judgment("") is None
    assert cd.parse_judgment("not json") is None
    assert cd.parse_judgment(json.dumps({"is_contradiction": "maybe"})) is None


# ───────────────────────── top_k_candidates ─────────────────────────


def test_top_k_picks_highest_similarity_first():
    target = [1.0, 0.0, 0.0]
    candidates = [
        ("close", [0.99, 0.10, 0.0]),
        ("far",   [0.10, 0.99, 0.0]),
        ("med",   [0.70, 0.10, 0.0]),
    ]
    out = cd.top_k_candidates(target, candidates, k=2, min_similarity=0.0)
    assert [cid for cid, _ in out] == ["close", "med"]


def test_top_k_drops_below_min_similarity():
    target = [1.0, 0.0]
    candidates = [
        ("a", [0.5, 0.0]),
        ("b", [0.05, 0.0]),
    ]
    out = cd.top_k_candidates(target, candidates, k=5, min_similarity=0.4)
    assert [cid for cid, _ in out] == ["a"]


def test_top_k_returns_empty_when_all_filtered():
    target = [1.0, 0.0]
    out = cd.top_k_candidates(target, [("x", [0.0, 1.0])], k=5, min_similarity=0.4)
    assert out == []


# ───────────────────────── existing_contradiction_for_pair ─────────────────────────


def test_existing_contradiction_for_pair_finds_match():
    """Round-trip via the seed: dedup helper must catch the seeded
    contradiction so re-runs skip it."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)
    from app.deps import session_scope
    with session_scope() as db:
        existing = cd.existing_contradiction_for_pair(
            db, "cl_invoice_march_total", "cl_invoice_april_total",
        )
        assert existing is not None
        assert existing.id == "cn_invoice_total_changed"
        # Order-independent
        existing2 = cd.existing_contradiction_for_pair(
            db, "cl_invoice_april_total", "cl_invoice_march_total",
        )
        assert existing2 is not None and existing2.id == existing.id

        none_match = cd.existing_contradiction_for_pair(
            db, "cl_master_signed", "cl_shipping_total",
        )
        assert none_match is None


# ───────────────────────── detect_for_file (DB-touching) ─────────────────────────


def test_detect_for_file_skips_when_llm_unreachable():
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=False)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=AssertionError("must not be called"))

    # Inject deterministic embeddings keyed by text length so we don't need
    # to load sentence-transformers in unit tests.
    def fake_embed(texts):
        return [_pseudo_vec(t) for t in texts]

    with patch.object(cd, "OllamaClient", return_value=fake):
        result = asyncio.run(cd.detect_for_file(
            "f_invoice_april", embed_fn=fake_embed,
        ))
    assert result.contradictions_created == 0
    assert result.pairs_judged == 0  # the LLM was never asked
    assert result.new_claims >= 1   # but the file's claims were loaded


def test_detect_for_file_persists_and_backlinks_both_claims():
    """Wipe seeded contradictions, run detection with mocked LLM that
    flags exactly the (March, April) invoice pair, assert both claims
    end up linked to the new Contradiction."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    from app.deps import session_scope
    from app.models.db import Claim, Contradiction
    with session_scope() as db:
        db.query(Contradiction).delete(synchronize_session=False)
        for cl in db.query(Claim).all():
            cl.contradiction_id = None

    def respond(prompt: str, **_) -> str:
        # Only flag pairs whose prompt mentions BOTH invoice totals.
        if "$4,500.00" in prompt and "$5,200.00" in prompt:
            return json.dumps({
                "is_contradiction": True,
                "topic": "Monthly invoice total",
                "severity": "high",
                "summary": "Different totals for the same line item.",
            })
        return json.dumps({"is_contradiction": False})

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=respond)

    # Embeddings: make march/april claims highly similar so they're
    # mutually top-K candidates.
    def fake_embed(texts):
        out = []
        for t in texts:
            if "March invoice" in t or "April invoice" in t:
                out.append([1.0, 0.05, 0.0])
            else:
                out.append([0.0, 1.0, 0.0])
        return out

    with patch.object(cd, "OllamaClient", return_value=fake):
        result = asyncio.run(cd.detect_for_file(
            "f_invoice_april", embed_fn=fake_embed,
        ))

    assert result.contradictions_created == 1
    assert result.duplicates_skipped == 0

    with session_scope() as db:
        contrs = db.query(Contradiction).all()
        assert len(contrs) == 1
        only = contrs[0]
        assert only.topic == "Monthly invoice total"
        assert only.severity == "high"
        # Both claim ids landed in the array
        ids_in_contr = set(json.loads(only.claim_ids_json))
        assert {"cl_invoice_march_total", "cl_invoice_april_total"} <= ids_in_contr
        # Both claims have contradiction_id set to this row
        for cid in ("cl_invoice_march_total", "cl_invoice_april_total"):
            cl = db.get(Claim, cid)
            assert cl is not None
            assert cl.contradiction_id == only.id


def test_detect_for_file_dedups_against_existing_contradiction():
    """The seed already contains the (March, April) contradiction. Running
    detection with an LLM that would re-flag it must NOT create a duplicate."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(return_value=json.dumps({
        "is_contradiction": True,
        "topic": "x", "severity": "high", "summary": "y",
    }))

    def fake_embed(texts):
        # Force every claim to look identical → all pairs become candidates.
        return [[1.0, 0.0, 0.0] for _ in texts]

    from app.deps import session_scope
    from app.models.db import Contradiction
    with session_scope() as db:
        before = db.query(Contradiction).count()

    with patch.object(cd, "OllamaClient", return_value=fake):
        result = asyncio.run(cd.detect_for_file(
            "f_invoice_april", embed_fn=fake_embed,
        ))

    with session_scope() as db:
        after = db.query(Contradiction).count()

    # The seeded (March, April) pair should have been skipped as duplicate;
    # any other pairs the LLM flagged would land as new rows.
    assert result.duplicates_skipped >= 1
    # Net new rows = after - before. Must equal contradictions_created.
    assert after - before == result.contradictions_created


def test_detect_for_file_excludes_same_chunk_pairs():
    """Two claims grounded in the same chunk should NEVER appear as a
    candidate pair — they're consistent by construction."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    # Add a second supported claim grounded in the same chunk as
    # cl_master_signed (which uses c_master_1).
    from app.deps import session_scope
    from app.models.db import Claim
    with session_scope() as db:
        sibling = Claim(
            id="cl_test_sibling",
            text="The agreement governs all production work.",
            status="supported",
            confidence=0.9,
            source_chunk_id="c_master_1",
            source_file_id="f_master_agreement",
            source_excerpt="governs all production work",
        )
        db.add(sibling)

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=AssertionError("no pair should be judged"))

    def fake_embed(texts):
        # Make both same-chunk claims look identical.
        return [[1.0, 0.0, 0.0] if "agreement" in t.lower() else [0.0, 1.0, 0.0] for t in texts]

    with patch.object(cd, "OllamaClient", return_value=fake):
        result = asyncio.run(cd.detect_for_file(
            "f_master_agreement", embed_fn=fake_embed,
        ))

    # Same-chunk pair filtered out before LLM call → no judgments.
    assert result.pairs_judged == 0


def test_detect_for_file_isolates_pair_errors():
    """One pair raising must not abort the others or fail the run."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    from app.deps import session_scope
    from app.models.db import Claim, Contradiction
    with session_scope() as db:
        db.query(Contradiction).delete(synchronize_session=False)
        for cl in db.query(Claim).all():
            cl.contradiction_id = None

    call_count = {"n": 0}

    def respond(prompt: str, **_) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise cd.LLMError("first pair blew up")
        return json.dumps({"is_contradiction": False})

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=respond)

    def fake_embed(texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    with patch.object(cd, "OllamaClient", return_value=fake):
        result = asyncio.run(cd.detect_for_file(
            "f_invoice_april", embed_fn=fake_embed,
        ))

    # The first call errored → counted as pair_error. Others ran.
    assert result.pair_errors >= 1
    assert result.pairs_judged + result.pair_errors == result.candidate_pairs


# ───────────────────────── helpers ─────────────────────────


def _pseudo_vec(s: str) -> list[float]:
    """Cheap hash-of-text → unit vector. Stable across runs."""
    h = sum(ord(c) for c in s) or 1
    return [
        ((h * 7) % 17) / 17.0,
        ((h * 11) % 23) / 23.0,
        ((h * 13) % 31) / 31.0,
    ]
