from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import get_session
from ..models.db import Chunk, File, QueryLog, TimelineEvent
from ..models.schemas import FileSummary

router = APIRouter(prefix="/files", tags=["files"])


@router.get("", response_model=list[FileSummary])
def list_files(
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> list[FileSummary]:
    stmt = select(File)
    if status:
        stmt = stmt.where(File.status == status)
    if source_type:
        stmt = stmt.where(File.source_type == source_type)
    if q:
        stmt = stmt.where(File.display_name.ilike(f"%{q}%"))
    stmt = stmt.order_by(File.ingested_at.desc()).limit(limit).offset(offset)
    files = db.execute(stmt).scalars().all()
    if not files:
        return []
    counts = dict(
        db.execute(
            select(Chunk.file_id, func.count(Chunk.id))
            .where(Chunk.file_id.in_([f.id for f in files]))
            .group_by(Chunk.file_id)
        ).all()
    )
    return [
        FileSummary(
            id=f.id, display_name=f.display_name, path=f.path,
            source_type=f.source_type, status=f.status, bytes=f.bytes,
            ingested_at=f.ingested_at, source_dt=f.source_dt,
            chunk_count=int(counts.get(f.id, 0)),
        )
        for f in files
    ]


@router.get("/{file_id}", response_model=FileSummary)
def get_file(file_id: str, db: Session = Depends(get_session)) -> FileSummary:
    f = db.get(File, file_id)
    if not f:
        raise HTTPException(status_code=404, detail="not found")
    cc = db.query(Chunk).filter(Chunk.file_id == f.id).count()
    return FileSummary(
        id=f.id, display_name=f.display_name, path=f.path,
        source_type=f.source_type, status=f.status, bytes=f.bytes,
        ingested_at=f.ingested_at, source_dt=f.source_dt, chunk_count=cc,
    )


@router.delete("/{file_id}")
def delete_file(file_id: str, db: Session = Depends(get_session)) -> dict:
    from ..deps import get_collection
    f = db.get(File, file_id)
    if not f:
        raise HTTPException(status_code=404, detail="not found")
    chunk_ids = [cid for (cid,) in db.execute(
        select(Chunk.id).where(Chunk.file_id == file_id)
    ).all()]
    db.delete(f)
    db.commit()
    if chunk_ids:
        try:
            get_collection().delete(ids=chunk_ids)
        except Exception:  # noqa: BLE001
            pass
    return {"deleted": True, "chunks_removed": len(chunk_ids)}


@router.get("/_/stats")
def stats(db: Session = Depends(get_session)) -> dict:
    files = db.query(File).count()
    chunks = db.query(Chunk).count()
    events = db.query(TimelineEvent).count()
    queries = db.query(QueryLog).count()
    refused = db.query(QueryLog).filter(QueryLog.refused == 1).count()
    by_type_rows = db.execute(
        select(File.source_type, func.count(File.id)).group_by(File.source_type)
    ).all()
    return {
        "files": files,
        "chunks": chunks,
        "timeline_events": events,
        "queries": queries,
        "refused": refused,
        "by_source_type": {k: int(v) for k, v in by_type_rows},
    }
