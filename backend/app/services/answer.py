from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.llm import OllamaClient, load_prompt  # noqa: E402

from ..config import Settings, get_settings
from ..deps import session_scope
from ..models.db import QueryLog
from ..models.schemas import AnswerResponse, Citation
from . import retrieval

log = logging.getLogger("evg.answer")

REFUSAL = "No supporting evidence found."
MIN_EXCERPT_CHARS = 12


def _build_evidence_block(chunks: list[retrieval.RetrievedChunk]) -> str:
    lines: list[str] = []
    for c in chunks:
        meta = f"file={c.file_name}; source_type={c.source_type}"
        if c.page is not None:
            meta += f"; page={c.page}"
        if c.source_dt is not None:
            meta += f"; date={c.source_dt.isoformat()}"
        body = c.text.replace("\n", " ").strip()
        lines.append(f"--- chunk_id: {c.chunk_id} ({meta}) ---\n{body}")
    return "\n\n".join(lines)


def _render_prompt(question: str, chunks: list[retrieval.RetrievedChunk]) -> str:
    template = load_prompt("answer_with_citations")
    block = _build_evidence_block(chunks)
    return template.replace("{{question}}", question).replace("{{evidence_block}}", block)


_THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


def _extract_json(s: str) -> Optional[dict]:
    if not s:
        return None
    s = _THINK_BLOCK.sub("", s)
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


def _validate(
    parsed: dict,
    chunks_by_id: dict[str, retrieval.RetrievedChunk],
) -> tuple[str, list[Citation], float]:
    """Apply the citation contract. Returns (answer, citations, confidence)."""
    answer = (parsed.get("answer") or "").strip()
    raw_cites = parsed.get("citations") or []
    if not isinstance(raw_cites, list):
        raw_cites = []

    if not answer or answer.lower() == REFUSAL.lower():
        return REFUSAL, [], 0.0

    cites: list[Citation] = []
    for rc in raw_cites:
        if not isinstance(rc, dict):
            continue
        cid = str(rc.get("chunk_id") or "").strip()
        excerpt = str(rc.get("excerpt") or "").strip()
        if cid not in chunks_by_id:
            continue
        if len(excerpt) < MIN_EXCERPT_CHARS:
            continue
        chunk = chunks_by_id[cid]
        if _normalize(excerpt) not in _normalize(chunk.text):
            log.debug("excerpt not substring of chunk %s; dropping citation", cid)
            continue
        cites.append(Citation(
            chunk_id=cid,
            file_id=chunk.file_id,
            file_name=chunk.file_name,
            file_path=chunk.file_path,
            source_type=chunk.source_type,
            source_dt=chunk.source_dt,
            page=chunk.page,
            ts_start_ms=chunk.ts_start_ms,
            ts_end_ms=chunk.ts_end_ms,
            excerpt=excerpt,
            score=chunk.score,
        ))

    if not cites:
        return REFUSAL, [], 0.0

    try:
        conf = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    if conf == 0.0:
        conf = round(min(1.0, sum(c.score for c in cites) / max(1, len(cites))), 3)
    return answer, cites, conf


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


async def answer_with_proof(
    question: str,
    *,
    k: Optional[int] = None,
    source_types: Optional[list[str]] = None,
    date_from=None,
    date_to=None,
    settings: Optional[Settings] = None,
) -> AnswerResponse:
    s = settings or get_settings()
    started = time.time()

    chunks = await asyncio.to_thread(
        retrieval.hybrid_search,
        question,
        k=k,
        source_types=source_types,
        date_from=date_from,
        date_to=date_to,
        settings=s,
    )
    if not chunks:
        return _refused(question, started)

    prompt = _render_prompt(question, chunks)
    client = OllamaClient(s.ollama_host, s.llm_model, s.llm_fallback_model)
    try:
        raw = await client.generate(prompt, format_json=False, temperature=0.0)
    except Exception as e:  # noqa: BLE001
        log.warning("LLM generate failed: %s", e)
        return _refused(question, started, err=True)
    finally:
        await client.aclose()

    parsed = _extract_json(raw)
    if not parsed:
        return _refused(question, started)

    chunks_by_id = {c.chunk_id: c for c in chunks}
    answer, cites, conf = _validate(parsed, chunks_by_id)
    refused = (not cites) or answer == REFUSAL
    elapsed_ms = int((time.time() - started) * 1000)
    _log_query(question, answer, [c.chunk_id for c in cites], refused, elapsed_ms)

    return AnswerResponse(
        answer=answer,
        citations=cites,
        confidence=conf,
        refused=refused,
        latency_ms=elapsed_ms,
    )


async def stream_answer(
    question: str,
    *,
    k: Optional[int] = None,
    source_types: Optional[list[str]] = None,
    date_from=None,
    date_to=None,
    settings: Optional[Settings] = None,
) -> AsyncIterator[dict]:
    """Streaming variant. Yields events:
       {type: 'retrieval', chunks: [...]}
       {type: 'token', text: '...'}        (for UX shimmer; final answer is 'final')
       {type: 'final', payload: AnswerResponse}
    """
    s = settings or get_settings()
    started = time.time()
    chunks = await asyncio.to_thread(
        retrieval.hybrid_search, question,
        k=k, source_types=source_types,
        date_from=date_from, date_to=date_to, settings=s,
    )
    yield {
        "type": "retrieval",
        "count": len(chunks),
        "chunk_ids": [c.chunk_id for c in chunks],
    }
    if not chunks:
        final = _refused(question, started)
        yield {"type": "final", "payload": final.model_dump(mode="json")}
        return

    prompt = _render_prompt(question, chunks)
    client = OllamaClient(s.ollama_host, s.llm_model, s.llm_fallback_model)
    buffer: list[str] = []
    try:
        async for tok in client.generate_stream(prompt, temperature=0.0):
            buffer.append(tok)
            yield {"type": "token", "text": tok}
    except Exception as e:  # noqa: BLE001
        log.warning("LLM stream failed: %s", e)
        final = _refused(question, started, err=True)
        yield {"type": "final", "payload": final.model_dump(mode="json")}
        return
    finally:
        await client.aclose()

    raw = "".join(buffer)
    parsed = _extract_json(raw)
    chunks_by_id = {c.chunk_id: c for c in chunks}
    if not parsed:
        final = _refused(question, started)
    else:
        answer, cites, conf = _validate(parsed, chunks_by_id)
        refused = (not cites) or answer == REFUSAL
        elapsed_ms = int((time.time() - started) * 1000)
        _log_query(question, answer, [c.chunk_id for c in cites], refused, elapsed_ms)
        final = AnswerResponse(
            answer=answer,
            citations=cites,
            confidence=conf,
            refused=refused,
            latency_ms=elapsed_ms,
        )
    yield {"type": "final", "payload": final.model_dump(mode="json")}


def _refused(question: str, started_at: float, err: bool = False) -> AnswerResponse:
    elapsed_ms = int((time.time() - started_at) * 1000)
    _log_query(question, REFUSAL, [], True, elapsed_ms)
    return AnswerResponse(
        answer=REFUSAL,
        citations=[],
        confidence=0.0,
        refused=True,
        latency_ms=elapsed_ms,
    )


def _log_query(question: str, answer: str, cited_ids: list[str],
               refused: bool, latency_ms: int) -> None:
    try:
        with session_scope() as db:
            db.add(QueryLog(
                id=str(uuid.uuid4()),
                question=question[:4000],
                answer=(answer or "")[:8000],
                cited_chunk_ids=json.dumps(cited_ids),
                refused=1 if refused else 0,
                latency_ms=latency_ms,
            ))
    except Exception as e:  # noqa: BLE001
        log.debug("query log failed: %s", e)
