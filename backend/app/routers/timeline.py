from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_session
from ..models.schemas import TimelineEventOut
from ..services.timeline import query_timeline

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("", response_model=list[TimelineEventOut])
def list_timeline(
    date_from: Optional[datetime] = Query(default=None, alias="from"),
    date_to: Optional[datetime] = Query(default=None, alias="to"),
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> list[TimelineEventOut]:
    return query_timeline(
        db,
        date_from=date_from,
        date_to=date_to,
        kind=kind,
        q=q,
        limit=limit,
        offset=offset,
    )
