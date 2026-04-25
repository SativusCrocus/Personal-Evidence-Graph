"""Per-claim obligation extractor.

Walks every "supported" claim that doesn't already have an obligation_id,
asks the local LLM to decide whether it's a commitment with a specific
counterparty + due date, and persists an Obligation row + back-link on
the Claim if so.

Mirrors claim_extraction.py's failure-isolation discipline: silent skip
when the LLM is unreachable, never raises into the ingestion pipeline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Keep ai/ importable when running under uvicorn or scripts.
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.llm import LLMError, OllamaClient, load_prompt  # noqa: E402

from ..config import Settings, get_settings
from ..deps import session_scope
from ..models.db import Chunk, Claim, File
from .claims import create_obligation, excerpt_in_chunk

log = logging.getLogger("evg.obligation_extraction")

PER_CLAIM_TIMEOUT_S = 30.0
CONCURRENCY = 3

_THINK = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class ObligationExtractionResult:
    file_id: Optional[str]
    claims_inspected: int
    obligations_created: int
    rejected_invalid: int
    claim_errors: int
    elapsed_ms: int


# ───────────────────────── prompt + parse ─────────────────────────


def _render_prompt(claim_text: str, chunk_text: str, file_source_dt: Optional[datetime]) -> str:
    template = load_prompt("extract_obligations")
    src = file_source_dt.date().isoformat() if file_source_dt else "unknown"
    return (
        template
        .replace("{{claim_text}}", claim_text)
        .replace("{{chunk_text}}", chunk_text)
        .replace("{{file_source_dt}}", src)
    )


def _extract_json(s: str) -> Optional[dict]:
    if not s:
        return None
    s = _THINK.sub("", s)
    s = _FENCE.sub("", s).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError:
        return None


def _parse_due_at(raw: str) -> Optional[datetime]:
    """Tolerate a few common LLM output shapes for ISO 8601."""
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        # Date-only fallback.
        try:
            dt = datetime.strptime(raw.strip(), "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_obligation(raw: str) -> Optional[dict]:
    """Pure function — pull a structured obligation out of an LLM response,
    or return None if the LLM said no / the response is malformed."""
    parsed = _extract_json(raw)
    if not isinstance(parsed, dict):
        return None
    if not parsed.get("is_obligation"):
        return None
    text = str(parsed.get("text") or "").strip()
    counterparty = str(parsed.get("counterparty") or "").strip()
    direction = str(parsed.get("direction") or "").strip().lower()
    excerpt = str(parsed.get("source_excerpt") or "").strip()
    due = _parse_due_at(str(parsed.get("due_at") or ""))
    if not text or not counterparty or direction not in ("incoming", "outgoing") or due is None:
        return None
    if len(excerpt) < 12:
        return None
    return {
        "text": text,
        "counterparty": counterparty,
        "direction": direction,
        "due_at": due,
        "source_excerpt": excerpt,
    }


# ───────────────────────── async core ─────────────────────────


async def _extract_one(client: OllamaClient, claim: Claim, chunk_text: str,
                       file_source_dt: Optional[datetime]) -> tuple[Optional[dict], Optional[str]]:
    prompt = _render_prompt(claim.text, chunk_text, file_source_dt)
    try:
        raw = await asyncio.wait_for(
            client.generate(prompt, format_json=True, temperature=0.0),
            timeout=PER_CLAIM_TIMEOUT_S,
        )
    except (asyncio.TimeoutError, LLMError, Exception) as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    return parse_obligation(raw), None


async def extract_for_file(
    file_id: str,
    *,
    settings: Optional[Settings] = None,
    skip_already_linked: bool = True,
) -> ObligationExtractionResult:
    """Inspect every supported claim for `file_id` and persist matching obligations."""
    s = settings or get_settings()
    started = time.time()

    with session_scope() as db:
        f = db.get(File, file_id)
        file_source_dt = f.source_dt if f else None
        q = (
            db.query(Claim, Chunk)
            .join(Chunk, Chunk.id == Claim.source_chunk_id)
            .filter(Claim.source_file_id == file_id, Claim.status == "supported")
        )
        if skip_already_linked:
            q = q.filter(Claim.obligation_id.is_(None))
        rows = [
            {"claim_id": cl.id, "claim_text": cl.text, "chunk_id": ch.id,
             "chunk_text": ch.text}
            for cl, ch in q.order_by(Claim.created_at.asc()).all()
        ]

    if not rows:
        return ObligationExtractionResult(
            file_id=file_id, claims_inspected=0, obligations_created=0,
            rejected_invalid=0, claim_errors=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )

    client = OllamaClient(s.ollama_host, s.llm_model, s.llm_fallback_model)
    if not await client.is_alive():
        await client.aclose()
        log.info("LLM at %s unreachable; skipping obligation extraction for %s",
                 s.ollama_host, file_id)
        return ObligationExtractionResult(
            file_id=file_id, claims_inspected=0, obligations_created=0,
            rejected_invalid=0, claim_errors=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _run(row):
        async with sem:
            # Re-fetch the Claim object so it's bound to a session-aware identity.
            stub = type("ClaimStub", (), {"text": row["claim_text"], "id": row["claim_id"]})
            ob, err = await _extract_one(client, stub, row["chunk_text"], file_source_dt)
            return row, ob, err

    try:
        results = await asyncio.gather(*[_run(r) for r in rows], return_exceptions=False)
    finally:
        await client.aclose()

    created = 0
    rejected = 0
    errors = 0
    with session_scope() as db:
        for row, ob, err in results:
            if err is not None:
                errors += 1
                log.warning("obligation extraction failed for claim %s: %s", row["claim_id"], err)
                continue
            if ob is None:
                continue
            # Belt-and-braces validation against the chunk we actually have in this session.
            chunk = db.get(Chunk, row["chunk_id"])
            if chunk is None or not excerpt_in_chunk(ob["source_excerpt"], chunk.text):
                rejected += 1
                continue
            try:
                obligation = create_obligation(
                    db,
                    text=ob["text"],
                    counterparty=ob["counterparty"],
                    direction=ob["direction"],
                    due_at=ob["due_at"],
                    status=_initial_status(ob["due_at"]),
                    claim_id=row["claim_id"],
                    source_chunk_id=row["chunk_id"],
                    source_file_id=file_id,
                    source_excerpt=ob["source_excerpt"],
                )
                # Back-link the claim → obligation.
                cl = db.get(Claim, row["claim_id"])
                if cl is not None:
                    cl.obligation_id = obligation.id
                created += 1
            except ValueError as ve:
                rejected += 1
                log.debug("create_obligation rejected: %s", ve)

    return ObligationExtractionResult(
        file_id=file_id,
        claims_inspected=len(rows),
        obligations_created=created,
        rejected_invalid=rejected,
        claim_errors=errors,
        elapsed_ms=int((time.time() - started) * 1000),
    )


def _initial_status(due_at: datetime) -> str:
    """Persist obligations with the right status at write-time. The
    /obligations endpoint also promotes open→overdue at read-time, so
    this is just a friendlier default for first-render."""
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return "overdue" if due_at < datetime.now(timezone.utc) else "open"


# ───────────────────────── sync entry for ingestion ─────────────────────────


def extract_for_file_sync(
    file_id: str,
    *,
    settings: Optional[Settings] = None,
) -> ObligationExtractionResult:
    """Sync wrapper for the ingestion pipeline. Never raises."""
    try:
        return asyncio.run(extract_for_file(file_id, settings=settings))
    except RuntimeError as e:
        log.warning("asyncio.run failed for obligations (file=%s): %s", file_id, e)
        return ObligationExtractionResult(
            file_id=file_id, claims_inspected=0, obligations_created=0,
            rejected_invalid=0, claim_errors=0, elapsed_ms=0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("obligation extraction crashed for file %s: %s", file_id, e)
        return ObligationExtractionResult(
            file_id=file_id, claims_inspected=0, obligations_created=0,
            rejected_invalid=0, claim_errors=0, elapsed_ms=0,
        )
