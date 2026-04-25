"""LLM-driven claim extractor.

Takes a chunk's text, asks the local LLM to enumerate factual claims with
verbatim source excerpts, and persists each one that survives the citation
contract (see services/claims.py::validate_claim).

Designed to be called per-file, batched across chunks, with hard isolation
between LLM failures and ingestion: if the LLM is unreachable or returns
garbage, the file still finishes ingesting — just without claims. The
extractor is strictly opt-in via Settings.extract_claims_during_ingest and
can be re-run later via scripts/extract_claims.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Make the ai/ sibling package importable when running under uvicorn.
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.llm import LLMError, OllamaClient, load_prompt  # noqa: E402

from ..config import Settings, get_settings
from ..deps import session_scope
from ..models.db import Chunk
from .claims import create_claim, validate_claim

log = logging.getLogger("evg.claim_extraction")

MAX_CHUNKS_PER_FILE_DEFAULT = 100
PER_CHUNK_TIMEOUT_S = 45.0
CONCURRENCY = 3

_THINK = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class ExtractionResult:
    file_id: str
    chunks_processed: int
    claims_created: int
    claims_dropped_invalid: int
    chunks_failed: int
    elapsed_ms: int


# ───────────────────────── prompt + parse ─────────────────────────


def _render_prompt(chunk_text: str) -> str:
    template = load_prompt("extract_claims")
    return template.replace("{{chunk_text}}", chunk_text)


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


def parse_candidates(raw: str) -> list[dict]:
    """Pull the claims array out of an LLM response. Pure function; no DB."""
    parsed = _extract_json(raw)
    if not isinstance(parsed, dict):
        return []
    items = parsed.get("claims")
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        text = str(it.get("text") or "").strip()
        excerpt = str(it.get("source_excerpt") or "").strip()
        try:
            confidence = float(it.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        out.append({
            "text": text,
            "source_excerpt": excerpt,
            "confidence": max(0.0, min(1.0, confidence)),
        })
    return out


# ───────────────────────── async core ─────────────────────────


async def _extract_one_chunk(
    client: OllamaClient,
    chunk: Chunk,
) -> tuple[list[dict], Optional[str]]:
    """Returns (validated_candidates, error_or_None)."""
    prompt = _render_prompt(chunk.text)
    try:
        raw = await asyncio.wait_for(
            client.generate(prompt, format_json=True, temperature=0.0),
            timeout=PER_CHUNK_TIMEOUT_S,
        )
    except (asyncio.TimeoutError, LLMError, Exception) as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"

    candidates = parse_candidates(raw)
    surviving: list[dict] = []
    for cand in candidates:
        ok, _reason = validate_claim(
            cand["text"], cand["source_excerpt"], chunk.text, cand["confidence"],
        )
        if ok:
            surviving.append(cand)
    return surviving, None


async def extract_for_file(
    file_id: str,
    *,
    settings: Optional[Settings] = None,
    skip_if_already_extracted: bool = True,
    max_chunks: int = MAX_CHUNKS_PER_FILE_DEFAULT,
) -> ExtractionResult:
    """Extract and persist claims for every chunk of `file_id`.

    Silent skip-and-return if the local LLM isn't reachable. Per-chunk
    failures don't abort the batch — they're counted and logged.
    """
    s = settings or get_settings()
    started = time.time()

    # Load chunk rows (snapshot — DB sessions don't survive the gather).
    with session_scope() as db:
        chunks = list(
            db.query(Chunk)
            .filter(Chunk.file_id == file_id)
            .order_by(Chunk.ord.asc())
            .limit(max_chunks)
        )
        if skip_if_already_extracted:
            from ..models.db import Claim
            already = {
                cid for (cid,) in db.query(Claim.source_chunk_id)
                .filter(Claim.source_chunk_id.in_([c.id for c in chunks]))
                .all()
            }
            chunks = [c for c in chunks if c.id not in already]

    if not chunks:
        return ExtractionResult(
            file_id=file_id, chunks_processed=0,
            claims_created=0, claims_dropped_invalid=0, chunks_failed=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )

    client = OllamaClient(s.ollama_host, s.llm_model, s.llm_fallback_model)
    if not await client.is_alive():
        await client.aclose()
        log.info("LLM at %s unreachable; skipping claim extraction for %s",
                 s.ollama_host, file_id)
        return ExtractionResult(
            file_id=file_id, chunks_processed=0,
            claims_created=0, claims_dropped_invalid=0, chunks_failed=0,
            elapsed_ms=int((time.time() - started) * 1000),
        )

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _run(c: Chunk):
        async with sem:
            return c, *(await _extract_one_chunk(client, c))

    try:
        results = await asyncio.gather(*[_run(c) for c in chunks], return_exceptions=False)
    finally:
        await client.aclose()

    created = 0
    dropped = 0
    failed = 0
    with session_scope() as db:
        for chunk, surviving, err in results:
            if err is not None:
                failed += 1
                log.warning("extraction failed for chunk %s: %s", chunk.id, err)
                continue
            # parse_candidates already filtered by validate_claim, so any drop
            # here was due to schema before validation. We track surviving only.
            for cand in surviving:
                try:
                    create_claim(
                        db,
                        text=cand["text"],
                        source_chunk_id=chunk.id,
                        source_file_id=chunk.file_id,
                        source_excerpt=cand["source_excerpt"],
                        confidence=cand["confidence"],
                        status="supported",
                        source_dt=None,  # promotion to source_dt is done by enrichment, not here
                    )
                    created += 1
                except ValueError as ve:
                    dropped += 1
                    log.debug("create_claim rejected: %s", ve)

    return ExtractionResult(
        file_id=file_id,
        chunks_processed=len(chunks),
        claims_created=created,
        claims_dropped_invalid=dropped,
        chunks_failed=failed,
        elapsed_ms=int((time.time() - started) * 1000),
    )


# ───────────────────────── sync entry for ingestion ─────────────────────────


def extract_for_file_sync(
    file_id: str,
    *,
    settings: Optional[Settings] = None,
) -> ExtractionResult:
    """Run the async extractor from sync code (e.g. the ingestion pipeline).
    Never raises — returns an empty-ish result if anything goes sideways.
    """
    try:
        return asyncio.run(extract_for_file(file_id, settings=settings))
    except RuntimeError as e:
        # Shouldn't happen from sync code, but guard against nested loops.
        log.warning("asyncio.run failed for extraction (file=%s): %s", file_id, e)
        return ExtractionResult(
            file_id=file_id, chunks_processed=0,
            claims_created=0, claims_dropped_invalid=0, chunks_failed=0,
            elapsed_ms=0,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("extraction crashed for file %s: %s", file_id, e)
        return ExtractionResult(
            file_id=file_id, chunks_processed=0,
            claims_created=0, claims_dropped_invalid=0, chunks_failed=0,
            elapsed_ms=0,
        )
