from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.llm import OllamaClient, load_prompt  # noqa: E402

from ..config import Settings, get_settings
from ..deps import session_scope
from ..models.db import Chunk, Enrichment, File, TimelineEvent

log = logging.getLogger("evg.enrichment")


async def enrich_file(file_id: str, settings: Optional[Settings] = None) -> int:
    """Run LLM enrichment on the first N chunks of a file. Cheap to skip; safe to retry."""
    s = settings or get_settings()
    template = load_prompt("enrich_metadata")
    client = OllamaClient(s.ollama_host, s.llm_model, s.llm_fallback_model)

    written = 0
    try:
        with session_scope() as db:
            f = db.get(File, file_id)
            if not f:
                return 0
            chunks = (
                db.query(Chunk)
                .filter(Chunk.file_id == file_id)
                .order_by(Chunk.ord.asc())
                .limit(8)
                .all()
            )
            file_name = f.display_name
            file_source_dt = f.source_dt

        for ch in chunks:
            prompt = template.replace("{{chunk_text}}", ch.text[:6000])
            try:
                raw = await client.generate(prompt, format_json=True, temperature=0.0)
            except Exception as e:  # noqa: BLE001
                log.debug("enrich generate failed: %s", e)
                continue
            try:
                data = json.loads(raw)
            except Exception:  # noqa: BLE001
                continue
            written += _persist_enrichment(file_id, ch.id, file_name, file_source_dt, data)
    finally:
        await client.aclose()
    return written


def _persist_enrichment(
    file_id: str,
    chunk_id: str,
    file_name: str,
    file_source_dt: Optional[datetime],
    data: dict,
) -> int:
    rows: list[Enrichment] = []
    events: list[TimelineEvent] = []

    summary = (data.get("summary") or "").strip()
    if summary:
        rows.append(Enrichment(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id,
            file_id=file_id,
            kind="summary",
            value=json.dumps({"text": summary[:300]}),
            confidence=0.7,
        ))

    for person in (data.get("people") or [])[:20]:
        name = (person or "").strip()
        if not name or len(name) > 120:
            continue
        rows.append(Enrichment(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id, file_id=file_id,
            kind="person", value=json.dumps({"name": name}), confidence=0.6,
        ))

    for d in (data.get("dates") or [])[:20]:
        if not isinstance(d, dict):
            continue
        ds = (d.get("date") or "").strip()
        ctx = (d.get("context") or "").strip()
        try:
            dt = datetime.fromisoformat(ds).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        rows.append(Enrichment(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id, file_id=file_id,
            kind="date",
            value=json.dumps({"date": ds, "context": ctx[:200]}),
            confidence=0.7,
        ))
        events.append(TimelineEvent(
            id=str(uuid.uuid4()),
            occurred_at=dt,
            file_id=file_id,
            chunk_id=chunk_id,
            title=(ctx or summary or file_name)[:200],
            description=summary[:1000] if summary else None,
            kind=(data.get("category") or None),
            confidence=0.7,
        ))

    for task in (data.get("tasks") or [])[:20]:
        t = (task or "").strip()
        if not t:
            continue
        rows.append(Enrichment(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id, file_id=file_id,
            kind="task", value=json.dumps({"text": t[:300]}), confidence=0.6,
        ))

    cat = (data.get("category") or "").strip()
    if cat:
        rows.append(Enrichment(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id, file_id=file_id,
            kind="category", value=json.dumps({"name": cat[:60]}), confidence=0.5,
        ))

    sent = (data.get("sentiment") or "").strip()
    if sent in {"positive", "neutral", "negative", "mixed"}:
        rows.append(Enrichment(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id, file_id=file_id,
            kind="sentiment", value=json.dumps({"label": sent}), confidence=0.5,
        ))

    if not events and file_source_dt is not None and (summary or cat):
        events.append(TimelineEvent(
            id=str(uuid.uuid4()),
            occurred_at=file_source_dt,
            file_id=file_id,
            chunk_id=chunk_id,
            title=(summary or file_name)[:200],
            description=None,
            kind=cat or None,
            confidence=0.4,
        ))

    if not rows and not events:
        return 0
    with session_scope() as db:
        for r in rows:
            db.add(r)
        for ev in events:
            db.add(ev)
    return len(rows) + len(events)
