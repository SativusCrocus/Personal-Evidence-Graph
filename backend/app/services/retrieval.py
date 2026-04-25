from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.embeddings import embed_one  # noqa: E402
from ai.reranker import rerank as ce_rerank  # noqa: E402

from ..config import Settings, get_settings
from ..deps import get_collection, session_scope
from ..models.db import Chunk, File

log = logging.getLogger("evg.retrieval")
_FTS_BAD = re.compile(r"[^\w\s]")
RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: str
    file_id: str
    file_name: str
    file_path: str
    source_type: str
    source_dt: Optional[datetime]
    text: str
    page: Optional[int]
    ts_start_ms: Optional[int]
    ts_end_ms: Optional[int]
    score: float


def _fts_query(q: str) -> str:
    """Build a safe FTS5 MATCH expression. Strip special chars; OR the tokens."""
    tokens = [t for t in _FTS_BAD.sub(" ", q).split() if len(t) > 1]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens[:32])


def _semantic_search(
    question: str,
    *,
    k: int,
    settings: Settings,
    where: Optional[dict] = None,
) -> list[tuple[str, float]]:
    coll = get_collection()
    vec = embed_one(question, settings.embed_model)
    res = coll.query(
        query_embeddings=[vec],
        n_results=k,
        where=where,
        include=["distances"],
    )
    ids = (res.get("ids") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    out: list[tuple[str, float]] = []
    for i, cid in enumerate(ids):
        d = dists[i] if i < len(dists) else 1.0
        sim = max(0.0, 1.0 - float(d))
        out.append((cid, sim))
    return out


def _keyword_search(question: str, db: Session, k: int) -> list[tuple[str, float]]:
    fts = _fts_query(question)
    if not fts:
        return []
    rows = db.execute(
        sql_text(
            """
            SELECT c.id, bm25(chunks_fts) AS score
            FROM chunks c
            JOIN chunks_fts f ON f.rowid = c.rowid
            WHERE chunks_fts MATCH :q
            ORDER BY score
            LIMIT :k
            """
        ),
        {"q": fts, "k": k},
    ).all()
    return [(r[0], 1.0 / (1.0 + max(0.0, float(r[1])))) for r in rows]


def _rrf_fuse(*runs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for run in runs:
        for rank, (cid, _) in enumerate(run):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _hydrate(
    db: Session,
    fused: list[tuple[str, float]],
    semantic: dict[str, float],
    limit: int,
) -> list[RetrievedChunk]:
    if not fused:
        return []
    ids = [cid for cid, _ in fused[:limit]]
    rows = (
        db.query(Chunk, File)
        .join(File, File.id == Chunk.file_id)
        .filter(Chunk.id.in_(ids))
        .all()
    )
    by_id = {ch.id: (ch, f) for ch, f in rows}
    out: list[RetrievedChunk] = []
    for cid, _rrf_score in fused[:limit]:
        if cid not in by_id:
            continue
        ch, f = by_id[cid]
        score = semantic.get(cid, 0.0)
        out.append(RetrievedChunk(
            chunk_id=ch.id,
            file_id=f.id,
            file_name=f.display_name,
            file_path=f.path,
            source_type=f.source_type,
            source_dt=f.source_dt,
            text=ch.text,
            page=ch.page,
            ts_start_ms=ch.ts_start_ms,
            ts_end_ms=ch.ts_end_ms,
            score=score,
        ))
    return out


def _apply_reranker(
    question: str,
    candidates: list[RetrievedChunk],
    settings: Settings,
) -> list[RetrievedChunk]:
    """Re-order candidates by a cross-encoder. Preserves the semantic-similarity
    .score field (used by the threshold gate downstream); the rerank score is
    only used for ordering. Identity-fallback if the model can't load.
    """
    if not settings.reranker_enabled or not candidates:
        return candidates
    pool = candidates[: settings.reranker_pool]
    tail = candidates[settings.reranker_pool:]
    try:
        ranked = ce_rerank(
            question,
            [c.text for c in pool],
            model_name=settings.reranker_model,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("reranker failed (%s); keeping first-stage order", e)
        return candidates
    # Identity fallback returns scores=0 for everything → preserve original order.
    if all(score == 0.0 for _idx, score in ranked):
        return candidates
    reordered = [pool[idx] for idx, _ in ranked]
    # Append anything beyond the rerank pool unchanged.
    return reordered + tail


def hybrid_search(
    question: str,
    *,
    k: Optional[int] = None,
    min_score: Optional[float] = None,
    source_types: Optional[list[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    settings: Optional[Settings] = None,
) -> list[RetrievedChunk]:
    s = settings or get_settings()
    final_k = k or s.retrieval_k
    final_min = s.retrieval_min_score if min_score is None else min_score
    pool = max(final_k * 4, 32)

    where: dict | None = None
    if source_types:
        where = {"source_type": {"$in": list(source_types)}}

    sem = _semantic_search(question, k=pool, settings=s, where=where)
    sem_map = {cid: sc for cid, sc in sem}

    with session_scope() as db:
        kw = _keyword_search(question, db, k=pool)
        fused = _rrf_fuse(sem, kw)
        hydrated = _hydrate(db, fused, sem_map, limit=pool)

    if date_from or date_to:
        def _ok(rc: RetrievedChunk) -> bool:
            if rc.source_dt is None:
                return False
            if date_from and rc.source_dt < date_from:
                return False
            if date_to and rc.source_dt > date_to:
                return False
            return True
        hydrated = [h for h in hydrated if _ok(h)]

    # Threshold gate uses semantic score (well-understood scale). The reranker
    # can promote a chunk inside the surviving set, but it can't rescue a chunk
    # that wasn't semantically close enough to clear the floor.
    filtered = [h for h in hydrated if h.score >= final_min]
    reranked = _apply_reranker(question, filtered, s)
    return reranked[:final_k]
