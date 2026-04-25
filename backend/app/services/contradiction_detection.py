"""Cross-claim contradiction detector.

For each newly-extracted claim, find the K most semantically similar
existing claims via embeddings, then ask the local LLM to judge each
candidate pair. Persist confirmed contradictions and back-link both
participating claims. Idempotent: re-running won't duplicate an existing
contradiction between the same pair.

Failure isolation matches claim/obligation extraction — silent skip when
the LLM is unreachable, and the embedding step alone never raises into
the ingestion pipeline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# Make ai/ importable when running under uvicorn or scripts.
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.embeddings import embed  # noqa: E402
from ai.llm import LLMError, OllamaClient, load_prompt  # noqa: E402

from ..config import Settings, get_settings
from ..deps import session_scope
from ..models.db import Chunk, Claim, Contradiction
from .claims import create_contradiction

log = logging.getLogger("evg.contradiction_detection")

PER_PAIR_TIMEOUT_S = 30.0
CONCURRENCY = 3
DEFAULT_TOP_K = 5
MIN_SIMILARITY = 0.40   # ignore candidates below this cosine sim — they're too unrelated
MAX_CLAIMS_PER_RUN = 2000

_THINK = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class DetectionResult:
    file_id: Optional[str]
    new_claims: int
    candidate_pairs: int
    pairs_judged: int
    contradictions_created: int
    duplicates_skipped: int
    pair_errors: int
    elapsed_ms: int


@dataclass
class _ClaimRow:
    """Snapshot used inside the async pipeline (detached from any DB session)."""
    id: str
    file_id: str
    chunk_id: str
    text: str
    chunk_text: str


# ───────────────────────── prompt + parse ─────────────────────────


def _render_prompt(claim_a: _ClaimRow, claim_b: _ClaimRow) -> str:
    template = load_prompt("judge_contradiction")
    return (
        template
        .replace("{{claim_a_text}}", claim_a.text)
        .replace("{{chunk_a_text}}", claim_a.chunk_text)
        .replace("{{claim_b_text}}", claim_b.text)
        .replace("{{chunk_b_text}}", claim_b.chunk_text)
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


def parse_judgment(raw: str) -> Optional[dict]:
    """Pure function — pull a structured contradiction judgment out of an
    LLM response. Returns None when the LLM said no, the response is
    malformed, or required fields are missing/blank."""
    parsed = _extract_json(raw)
    if not isinstance(parsed, dict):
        return None
    if not parsed.get("is_contradiction"):
        return None
    topic = str(parsed.get("topic") or "").strip()
    summary = str(parsed.get("summary") or "").strip()
    severity = str(parsed.get("severity") or "medium").strip().lower()
    if severity not in ("low", "medium", "high"):
        severity = "medium"
    if not topic or not summary:
        return None
    return {"topic": topic, "summary": summary, "severity": severity}


# ───────────────────────── K-NN over claim embeddings ─────────────────────────


def _cosine(a: list[float], b: list[float]) -> float:
    """Plain dot-product since ai.embeddings normalizes outputs to unit length."""
    return sum(x * y for x, y in zip(a, b))


def top_k_candidates(
    target_vec: list[float],
    candidates: list[tuple[str, list[float]]],
    *,
    k: int = DEFAULT_TOP_K,
    min_similarity: float = MIN_SIMILARITY,
) -> list[tuple[str, float]]:
    """Return the K candidate ids most similar to target_vec, descending."""
    scored = [(cid, _cosine(target_vec, cv)) for cid, cv in candidates]
    scored = [(cid, sim) for cid, sim in scored if sim >= min_similarity]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ───────────────────────── DB helpers ─────────────────────────


_DETECTABLE_STATUSES = ("supported", "contradicted")


def _load_claim_rows(db, *, ids: Optional[Iterable[str]] = None) -> list[_ClaimRow]:
    # Include claims that have already been flagged as contradicted —
    # dedup happens later, and a previously-contradicted claim may still
    # conflict with new ones we haven't compared it against.
    q = db.query(Claim, Chunk).join(Chunk, Chunk.id == Claim.source_chunk_id).filter(
        Claim.status.in_(_DETECTABLE_STATUSES)
    )
    if ids is not None:
        ids = list(ids)
        if not ids:
            return []
        q = q.filter(Claim.id.in_(ids))
    out: list[_ClaimRow] = []
    for cl, ch in q.limit(MAX_CLAIMS_PER_RUN).all():
        out.append(_ClaimRow(
            id=cl.id, file_id=cl.source_file_id, chunk_id=ch.id,
            text=cl.text, chunk_text=ch.text,
        ))
    return out


def existing_contradiction_for_pair(
    db, claim_a_id: str, claim_b_id: str,
) -> Optional[Contradiction]:
    """O(N) scan over contradictions; N is sparse in practice. Returns the
    first contradiction whose claim_ids array contains both ids, or None."""
    target = {claim_a_id, claim_b_id}
    for r in db.query(Contradiction).all():
        try:
            ids = set(json.loads(r.claim_ids_json or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if target.issubset(ids):
            return r
    return None


# ───────────────────────── async core ─────────────────────────


async def _judge_pair(
    client: OllamaClient,
    a: _ClaimRow,
    b: _ClaimRow,
) -> tuple[Optional[dict], Optional[str]]:
    prompt = _render_prompt(a, b)
    try:
        raw = await asyncio.wait_for(
            client.generate(prompt, format_json=True, temperature=0.0),
            timeout=PER_PAIR_TIMEOUT_S,
        )
    except (asyncio.TimeoutError, LLMError, Exception) as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    return parse_judgment(raw), None


async def detect_for_file(
    file_id: str,
    *,
    settings: Optional[Settings] = None,
    k: int = DEFAULT_TOP_K,
    embed_fn=None,
) -> DetectionResult:
    """Detect contradictions between every supported claim from `file_id`
    and the rest of the corpus. Idempotent.

    `embed_fn` is injectable for tests; defaults to ai.embeddings.embed.
    """
    s = settings or get_settings()
    started = time.time()
    embedder = embed_fn or (lambda texts: embed(texts, s.embed_model))

    with session_scope() as db:
        new_rows = _load_claim_rows(
            db,
            ids=[cid for (cid,) in db.query(Claim.id).filter(
                Claim.source_file_id == file_id,
                Claim.status.in_(_DETECTABLE_STATUSES),
            ).all()],
        )
        all_rows = _load_claim_rows(db)

    if not new_rows:
        return DetectionResult(
            file_id=file_id, new_claims=0, candidate_pairs=0,
            pairs_judged=0, contradictions_created=0,
            duplicates_skipped=0, pair_errors=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )

    # Embed every claim text in one batch — cheap enough for v1, can move
    # to a persistent vector store later.
    texts = [r.text for r in all_rows]
    try:
        vectors = embedder(texts)
    except Exception as e:  # noqa: BLE001
        log.warning("claim embedding failed for %s: %s", file_id, e)
        return DetectionResult(
            file_id=file_id, new_claims=len(new_rows), candidate_pairs=0,
            pairs_judged=0, contradictions_created=0,
            duplicates_skipped=0, pair_errors=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )
    by_id = {row.id: vec for row, vec in zip(all_rows, vectors)}
    rows_by_id = {row.id: row for row in all_rows}

    # Build candidate pairs: each new claim → top-K most similar non-self,
    # different-chunk rows. Same-chunk claims are consistent by construction.
    pairs: list[tuple[_ClaimRow, _ClaimRow, float]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for new in new_rows:
        if new.id not in by_id:
            continue
        candidates = [
            (cid, vec) for cid, vec in by_id.items()
            if cid != new.id and rows_by_id[cid].chunk_id != new.chunk_id
        ]
        for cid, sim in top_k_candidates(by_id[new.id], candidates, k=k):
            key = tuple(sorted([new.id, cid]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            pairs.append((new, rows_by_id[cid], sim))

    if not pairs:
        return DetectionResult(
            file_id=file_id, new_claims=len(new_rows), candidate_pairs=0,
            pairs_judged=0, contradictions_created=0,
            duplicates_skipped=0, pair_errors=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )

    client = OllamaClient(s.ollama_host, s.llm_model, s.llm_fallback_model)
    if not await client.is_alive():
        await client.aclose()
        log.info("LLM at %s unreachable; skipping contradiction detection for %s",
                 s.ollama_host, file_id)
        return DetectionResult(
            file_id=file_id, new_claims=len(new_rows),
            candidate_pairs=len(pairs), pairs_judged=0,
            contradictions_created=0, duplicates_skipped=0, pair_errors=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _run(pair):
        a, b, _sim = pair
        async with sem:
            judgment, err = await _judge_pair(client, a, b)
            return a, b, judgment, err

    try:
        results = await asyncio.gather(*[_run(p) for p in pairs])
    finally:
        await client.aclose()

    created = 0
    duplicates = 0
    errors = 0
    pairs_judged = 0
    with session_scope() as db:
        for a, b, judgment, err in results:
            if err is not None:
                errors += 1
                log.warning("contradiction judge failed for (%s, %s): %s",
                            a.id, b.id, err)
                continue
            pairs_judged += 1
            if judgment is None:
                continue
            existing = existing_contradiction_for_pair(db, a.id, b.id)
            if existing is not None:
                duplicates += 1
                continue
            try:
                contr = create_contradiction(
                    db,
                    topic=judgment["topic"],
                    summary=judgment["summary"],
                    severity=judgment["severity"],
                    claim_ids=[a.id, b.id],
                    related_chunk_ids=[a.chunk_id, b.chunk_id],
                )
                # Back-link both claims (most-recent wins; canonical
                # truth lives in Contradiction.claim_ids_json).
                for cid in (a.id, b.id):
                    cl = db.get(Claim, cid)
                    if cl is not None:
                        cl.contradiction_id = contr.id
                created += 1
            except ValueError as ve:
                errors += 1
                log.debug("create_contradiction rejected: %s", ve)

    return DetectionResult(
        file_id=file_id,
        new_claims=len(new_rows),
        candidate_pairs=len(pairs),
        pairs_judged=pairs_judged,
        contradictions_created=created,
        duplicates_skipped=duplicates,
        pair_errors=errors,
        elapsed_ms=int((time.time() - started) * 1000),
    )


# ───────────────────────── sync entry for ingestion ─────────────────────────


def detect_for_file_sync(
    file_id: str,
    *,
    settings: Optional[Settings] = None,
) -> DetectionResult:
    """Sync wrapper for the ingestion pipeline. Never raises."""
    try:
        return asyncio.run(detect_for_file(file_id, settings=settings))
    except RuntimeError as e:
        log.warning("asyncio.run failed for contradictions (file=%s): %s", file_id, e)
        return DetectionResult(
            file_id=file_id, new_claims=0, candidate_pairs=0,
            pairs_judged=0, contradictions_created=0,
            duplicates_skipped=0, pair_errors=0, elapsed_ms=0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("contradiction detection crashed for file %s: %s", file_id, e)
        return DetectionResult(
            file_id=file_id, new_claims=0, candidate_pairs=0,
            pairs_judged=0, contradictions_created=0,
            duplicates_skipped=0, pair_errors=0, elapsed_ms=0,
        )


# Used in tests to silence the integer normalization warning when math.isnan.
_ = math.isnan
