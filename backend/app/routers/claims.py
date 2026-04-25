from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_session
from ..models.schemas import (
    ClaimOut,
    ContradictionOut,
    ObligationOut,
    PipelineEventOut,
)
from ..services.claims import (
    list_claims,
    list_contradictions,
    list_obligations,
    list_pipeline_events,
)

router = APIRouter(tags=["claims"])


@router.get("/claims", response_model=list[ClaimOut])
def get_claims(
    status: Optional[str] = None,
    file_id: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> list[ClaimOut]:
    return list_claims(db, status=status, file_id=file_id, limit=limit, offset=offset)


@router.get("/contradictions", response_model=list[ContradictionOut])
def get_contradictions(
    severity: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> list[ContradictionOut]:
    return list_contradictions(db, severity=severity, limit=limit, offset=offset)


@router.get("/obligations", response_model=list[ObligationOut])
def get_obligations(
    status: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> list[ObligationOut]:
    return list_obligations(db, status=status, limit=limit, offset=offset)


@router.get("/pipeline/events", response_model=list[PipelineEventOut])
def get_pipeline_events(
    file_id: Optional[str] = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> list[PipelineEventOut]:
    return list_pipeline_events(db, file_id=file_id, limit=limit, offset=offset)
