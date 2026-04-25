from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.db import (
    Chunk,
    Claim,
    Contradiction,
    File,
    Obligation,
    PipelineEvent,
)
from ..models.schemas import (
    ClaimOut,
    ContradictionOut,
    ObligationOut,
    PipelineEventOut,
)


# ───────────────────────── citation validation ─────────────────────────


_WHITESPACE = re.compile(r"\s+")


def _normalize(s: str) -> str:
    """Collapse whitespace + lowercase. Used to verify excerpt-in-chunk match."""
    return _WHITESPACE.sub(" ", s).strip().lower()


def excerpt_in_chunk(excerpt: str, chunk_text: str) -> bool:
    """The citation contract for claims: the excerpt must be a substring of
    the chunk it claims to come from, modulo whitespace and case. Empty
    excerpts always fail. Useful both at extraction time and at audit time.
    """
    if not excerpt or not chunk_text:
        return False
    return _normalize(excerpt) in _normalize(chunk_text)


def validate_claim(
    claim_text: str,
    excerpt: str,
    chunk_text: str,
    confidence: float,
) -> tuple[bool, Optional[str]]:
    """Return (ok, reason). Reason is None when ok."""
    if not claim_text.strip():
        return False, "empty claim text"
    if not (0.0 <= confidence <= 1.0):
        return False, f"confidence {confidence} out of [0,1]"
    if not excerpt_in_chunk(excerpt, chunk_text):
        return False, "excerpt not present in source chunk (verbatim required)"
    return True, None


# ───────────────────────── reads ─────────────────────────


def list_claims(
    db: Session,
    *,
    status: Optional[str] = None,
    file_id: Optional[str] = None,
    chunk_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[ClaimOut]:
    stmt = select(Claim)
    if status:
        stmt = stmt.where(Claim.status == status)
    if file_id:
        stmt = stmt.where(Claim.source_file_id == file_id)
    if chunk_id:
        stmt = stmt.where(Claim.source_chunk_id == chunk_id)
    stmt = stmt.order_by(Claim.created_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return [ClaimOut.model_validate(r) for r in rows]


def list_contradictions(
    db: Session,
    *,
    severity: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[ContradictionOut]:
    stmt = select(Contradiction)
    if severity:
        stmt = stmt.where(Contradiction.severity == severity)
    stmt = stmt.order_by(Contradiction.detected_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    out: list[ContradictionOut] = []
    for r in rows:
        out.append(
            ContradictionOut(
                id=r.id,
                topic=r.topic,
                summary=r.summary,
                severity=r.severity,  # type: ignore[arg-type]
                detected_at=r.detected_at,
                claim_ids=_safe_json_list(r.claim_ids_json),
                related_chunk_ids=_safe_json_list(r.related_chunk_ids_json),
            )
        )
    return out


def list_obligations(
    db: Session,
    *,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[ObligationOut]:
    stmt = select(Obligation)
    if status:
        stmt = stmt.where(Obligation.status == status)
    stmt = stmt.order_by(Obligation.due_at.asc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    out: list[ObligationOut] = []
    now = datetime.now(timezone.utc)
    for r in rows:
        # Promote open → overdue when due_at has passed; persist nothing.
        status_out = r.status
        due = r.due_at
        if due is not None and status_out == "open":
            due_aware = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
            if due_aware < now:
                status_out = "overdue"
        out.append(
            ObligationOut(
                id=r.id, text=r.text, counterparty=r.counterparty,
                direction=r.direction,  # type: ignore[arg-type]
                due_at=r.due_at,
                status=status_out,  # type: ignore[arg-type]
                claim_id=r.claim_id,
                source_chunk_id=r.source_chunk_id,
                source_file_id=r.source_file_id,
                source_excerpt=r.source_excerpt,
            )
        )
    return out


def list_pipeline_events(
    db: Session,
    *,
    file_id: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
) -> list[PipelineEventOut]:
    stmt = select(PipelineEvent)
    if file_id:
        stmt = stmt.where(PipelineEvent.file_id == file_id)
    stmt = stmt.order_by(PipelineEvent.at.asc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return [PipelineEventOut.model_validate(r) for r in rows]


# ───────────────────────── writes (used by seed + future extractor) ─────────────────────────


def create_claim(
    db: Session,
    *,
    text: str,
    source_chunk_id: str,
    source_file_id: str,
    source_excerpt: str,
    confidence: float,
    status: str = "supported",
    source_dt: Optional[datetime] = None,
    contradiction_id: Optional[str] = None,
    obligation_id: Optional[str] = None,
    claim_id: Optional[str] = None,
) -> Claim:
    """Persist a claim after validating the citation contract."""
    chunk = db.get(Chunk, source_chunk_id)
    if chunk is None:
        raise ValueError(f"unknown chunk {source_chunk_id}")
    file_ = db.get(File, source_file_id)
    if file_ is None:
        raise ValueError(f"unknown file {source_file_id}")
    ok, reason = validate_claim(text, source_excerpt, chunk.text, confidence)
    if not ok:
        raise ValueError(f"invalid claim: {reason}")

    cl = Claim(
        text=text,
        status=status,
        confidence=confidence,
        source_chunk_id=source_chunk_id,
        source_file_id=source_file_id,
        source_excerpt=source_excerpt,
        source_dt=source_dt,
        contradiction_id=contradiction_id,
        obligation_id=obligation_id,
    )
    if claim_id:
        cl.id = claim_id
    db.add(cl)
    db.flush()
    return cl


def create_contradiction(
    db: Session,
    *,
    topic: str,
    summary: str,
    severity: str,
    claim_ids: Iterable[str],
    related_chunk_ids: Iterable[str] = (),
    detected_at: Optional[datetime] = None,
    contradiction_id: Optional[str] = None,
) -> Contradiction:
    c = Contradiction(
        topic=topic,
        summary=summary,
        severity=severity,
        claim_ids_json=json.dumps(list(claim_ids)),
        related_chunk_ids_json=json.dumps(list(related_chunk_ids)),
    )
    if detected_at is not None:
        c.detected_at = detected_at
    if contradiction_id:
        c.id = contradiction_id
    db.add(c)
    db.flush()
    return c


def create_obligation(
    db: Session,
    *,
    text: str,
    counterparty: str,
    direction: str,
    due_at: datetime,
    status: str,
    claim_id: str,
    source_chunk_id: str,
    source_file_id: str,
    source_excerpt: str,
    obligation_id: Optional[str] = None,
) -> Obligation:
    o = Obligation(
        text=text,
        counterparty=counterparty,
        direction=direction,
        due_at=due_at,
        status=status,
        claim_id=claim_id,
        source_chunk_id=source_chunk_id,
        source_file_id=source_file_id,
        source_excerpt=source_excerpt,
    )
    if obligation_id:
        o.id = obligation_id
    db.add(o)
    db.flush()
    return o


def record_pipeline_event(
    db: Session,
    *,
    file_id: str,
    stage: str,
    status: str,
    message: Optional[str] = None,
    at: Optional[datetime] = None,
    event_id: Optional[str] = None,
) -> PipelineEvent:
    e = PipelineEvent(
        file_id=file_id,
        stage=stage,
        status=status,
        message=message,
    )
    if at is not None:
        e.at = at
    if event_id:
        e.id = event_id
    db.add(e)
    db.flush()
    return e


# ───────────────────────── helpers ─────────────────────────


def _safe_json_list(s: Optional[str]) -> list[str]:
    if not s:
        return []
    try:
        v = json.loads(s)
        return [str(x) for x in v] if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []
