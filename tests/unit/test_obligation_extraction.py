"""Unit tests for the per-claim obligation extractor.

Mocks the LLM everywhere — no network. Verifies each judgment path:
  - positive (commitment with date + counterparty + direction)
  - claim is just a fact, not a commitment
  - LLM-supplied excerpt is paraphrased (not in the chunk) → rejected
  - missing due_at, malformed direction → rejected
  - silent skip when LLM is_alive=False
  - end-to-end: obligation row persists AND claim.obligation_id is set
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.services import obligation_extraction as oe


CHUNK_TEXT = (
    "Owner: Just to confirm — you said the April run will be ready by the 15th, right? "
    "Sequoia rep: Yes, absolutely. We'll have everything packed and out the door by April 15th. "
    "You'll see a UPS tracking number that day."
)


def _llm_returns(payload: dict | str):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    client = AsyncMock()
    client.is_alive = AsyncMock(return_value=True)
    client.generate = AsyncMock(return_value=raw)
    client.aclose = AsyncMock(return_value=None)
    return client


# ───────────────────────── parse_obligation ─────────────────────────


def test_parse_obligation_clean_positive():
    raw = json.dumps({
        "is_obligation": True,
        "text": "Sequoia delivers April run",
        "counterparty": "Sequoia Print Co",
        "direction": "incoming",
        "due_at": "2026-04-15T23:59:00Z",
        "source_excerpt": "out the door by April 15th",
    })
    out = oe.parse_obligation(raw)
    assert out is not None
    assert out["counterparty"] == "Sequoia Print Co"
    assert out["direction"] == "incoming"
    assert out["due_at"] == datetime(2026, 4, 15, 23, 59, tzinfo=timezone.utc)


def test_parse_obligation_returns_none_for_negative():
    assert oe.parse_obligation(json.dumps({"is_obligation": False})) is None


def test_parse_obligation_rejects_missing_required_fields():
    assert oe.parse_obligation(json.dumps({
        "is_obligation": True, "text": "x", "due_at": "2026-04-15"
        # missing counterparty + direction + source_excerpt
    })) is None


def test_parse_obligation_rejects_bad_direction():
    raw = json.dumps({
        "is_obligation": True,
        "text": "x", "counterparty": "y", "direction": "sideways",
        "due_at": "2026-04-15T00:00:00Z", "source_excerpt": "out the door",
    })
    assert oe.parse_obligation(raw) is None


def test_parse_obligation_rejects_unparseable_due_at():
    raw = json.dumps({
        "is_obligation": True,
        "text": "x", "counterparty": "y", "direction": "incoming",
        "due_at": "sometime next month",
        "source_excerpt": "out the door by April 15th",
    })
    assert oe.parse_obligation(raw) is None


def test_parse_obligation_rejects_short_excerpt():
    raw = json.dumps({
        "is_obligation": True,
        "text": "x", "counterparty": "y", "direction": "incoming",
        "due_at": "2026-04-15T00:00:00Z",
        "source_excerpt": "ok",
    })
    assert oe.parse_obligation(raw) is None


def test_parse_obligation_handles_date_only_due_at():
    raw = json.dumps({
        "is_obligation": True,
        "text": "x", "counterparty": "y", "direction": "outgoing",
        "due_at": "2026-04-15",
        "source_excerpt": "out the door by April 15th",
    })
    out = oe.parse_obligation(raw)
    assert out is not None
    # Date-only strings get UTC midnight by datetime.fromisoformat handling.
    assert out["due_at"].year == 2026
    assert out["due_at"].month == 4
    assert out["due_at"].day == 15


def test_parse_obligation_garbled_response_returns_none():
    assert oe.parse_obligation("not json at all") is None
    assert oe.parse_obligation("") is None


# ───────────────────────── _extract_one ─────────────────────────


class _ClaimStub:
    def __init__(self, id: str, text: str):
        self.id = id
        self.text = text


def _run(coro):
    return asyncio.run(coro)


def test_extract_one_positive_path():
    client = _llm_returns({
        "is_obligation": True,
        "text": "Sequoia delivers April run",
        "counterparty": "Sequoia Print Co",
        "direction": "incoming",
        "due_at": "2026-04-15T23:59:00Z",
        "source_excerpt": "out the door by April 15th",
    })
    out, err = _run(oe._extract_one(
        client, _ClaimStub("c", "Sequoia delivers April run"),
        CHUNK_TEXT, datetime(2026, 4, 8, tzinfo=timezone.utc),
    ))
    assert err is None
    assert out is not None
    assert out["counterparty"] == "Sequoia Print Co"


def test_extract_one_negative_returns_none_no_error():
    client = _llm_returns({"is_obligation": False})
    out, err = _run(oe._extract_one(
        client, _ClaimStub("c", "Invoice total is $5,200."),
        "INVOICE — Total: $5,200.00", None,
    ))
    assert err is None
    assert out is None


def test_extract_one_llm_error_surfaces_in_err():
    client = AsyncMock()
    client.is_alive = AsyncMock(return_value=True)
    client.generate = AsyncMock(side_effect=oe.LLMError("connection refused"))
    client.aclose = AsyncMock(return_value=None)
    out, err = _run(oe._extract_one(
        client, _ClaimStub("c", "x"), CHUNK_TEXT, None,
    ))
    assert out is None
    assert err is not None
    assert "LLMError" in err or "connection refused" in err


# ───────────────────────── extract_for_file (DB-touching) ─────────────────────────


def test_extract_for_file_skips_when_llm_unreachable():
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=False)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=AssertionError("must not be called"))
    with patch.object(oe, "OllamaClient", return_value=fake):
        result = asyncio.run(oe.extract_for_file("f_voicememo_call"))
    assert result.claims_inspected == 0
    assert result.obligations_created == 0


def test_extract_for_file_persists_obligation_and_links_back_to_claim():
    """End-to-end: when the LLM judges a claim to be an obligation, we
    persist an Obligation row, set claim.obligation_id, and the resulting
    obligation's status reflects whether due_at is past."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    # Wipe the seeded obligation + the claim's existing back-link so the
    # delta is deterministic for this test.
    from app.deps import session_scope
    from app.models.db import Claim, Obligation
    with session_scope() as db:
        db.query(Obligation).delete(synchronize_session=False)
        for cl in db.query(Claim).all():
            cl.obligation_id = None

    # Mock returns positive only for the delivery claim, negative for everything else.
    def respond(prompt: str, **_) -> str:
        if "Sequoia Print Co will deliver" in prompt or "April production run" in prompt:
            return json.dumps({
                "is_obligation": True,
                "text": "Sequoia Print Co to deliver April production run",
                "counterparty": "Sequoia Print Co",
                "direction": "incoming",
                "due_at": "2026-04-15T23:59:00Z",
                "source_excerpt": "out the door by April 15th",
            })
        return json.dumps({"is_obligation": False})

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(side_effect=respond)

    with patch.object(oe, "OllamaClient", return_value=fake):
        result = asyncio.run(oe.extract_for_file("f_voicememo_call"))

    assert result.obligations_created == 1
    assert result.claim_errors == 0

    with session_scope() as db:
        obligations = db.query(Obligation).all()
        assert len(obligations) == 1
        ob = obligations[0]
        assert ob.counterparty == "Sequoia Print Co"
        assert ob.direction == "incoming"
        # April 15 2026 is past 2026-04-25 → status persisted as "overdue".
        assert ob.status == "overdue"

        # The seeded delivery claim now back-links to the new obligation.
        cl = db.get(Claim, "cl_delivery_april_15")
        assert cl is not None
        assert cl.obligation_id == ob.id


def test_extract_for_file_rejects_paraphrased_excerpt():
    """Belt-and-braces: even if parse_obligation lets a long-enough excerpt
    through, the chunk-text check inside extract_for_file rejects anything
    that doesn't verbatim match. Pins the citation contract end-to-end."""
    from scripts import seed_demo  # type: ignore[attr-defined]
    seed_demo.seed(reset=True, dry_run=False)

    from app.deps import session_scope
    from app.models.db import Claim, Obligation
    with session_scope() as db:
        db.query(Obligation).delete(synchronize_session=False)
        for cl in db.query(Claim).all():
            cl.obligation_id = None

    fake = AsyncMock()
    fake.is_alive = AsyncMock(return_value=True)
    fake.aclose = AsyncMock(return_value=None)
    fake.generate = AsyncMock(return_value=json.dumps({
        "is_obligation": True,
        "text": "Sequoia delivers April run",
        "counterparty": "Sequoia Print Co",
        "direction": "incoming",
        "due_at": "2026-04-15T23:59:00Z",
        # Long enough to pass the parse-time length check, but NOT in the chunk.
        "source_excerpt": "Sequoia hereby commits to delivery on or before April 15",
    }))

    with patch.object(oe, "OllamaClient", return_value=fake):
        result = asyncio.run(oe.extract_for_file("f_voicememo_call"))

    assert result.obligations_created == 0
    assert result.rejected_invalid >= 1
