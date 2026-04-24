from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from ..models.db import File, TimelineEvent
from ..models.schemas import TimelineEventOut


def query_timeline(
    db: Session,
    *,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TimelineEventOut]:
    filters = []
    if date_from:
        filters.append(TimelineEvent.occurred_at >= date_from)
    if date_to:
        filters.append(TimelineEvent.occurred_at <= date_to)
    if kind:
        filters.append(TimelineEvent.kind == kind)
    if q:
        ql = f"%{q.lower()}%"
        filters.append(TimelineEvent.title.ilike(ql))

    stmt = (
        select(TimelineEvent, File)
        .join(File, File.id == TimelineEvent.file_id)
        .where(and_(*filters) if filters else True)
        .order_by(TimelineEvent.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).all()
    out: list[TimelineEventOut] = []
    for ev, f in rows:
        out.append(TimelineEventOut(
            id=ev.id,
            occurred_at=ev.occurred_at,
            title=ev.title,
            description=ev.description,
            kind=ev.kind,
            file_id=f.id,
            chunk_id=ev.chunk_id,
            file_name=f.display_name,
            source_type=f.source_type,
            confidence=ev.confidence,
        ))
    return out
