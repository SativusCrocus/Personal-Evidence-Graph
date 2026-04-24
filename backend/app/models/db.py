from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    mime: Mapped[str] = mapped_column(String, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    source_dt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    enrichments: Mapped[list["Enrichment"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('pdf','image','audio','text','browser','clipboard','video','other')",
            name="ck_files_source_type",
        ),
        CheckConstraint(
            "status IN ('pending','extracting','enriching','indexed','failed')",
            name="ck_files_status",
        ),
        Index("idx_files_source_dt", "source_dt"),
        Index("idx_files_status", "status"),
        Index("idx_files_type", "source_type"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    file_id: Mapped[str] = mapped_column(
        String, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[Optional[int]] = mapped_column(Integer)
    char_end: Mapped[Optional[int]] = mapped_column(Integer)
    page: Mapped[Optional[int]] = mapped_column(Integer)
    ts_start_ms: Mapped[Optional[int]] = mapped_column(Integer)
    ts_end_ms: Mapped[Optional[int]] = mapped_column(Integer)
    tokens: Mapped[Optional[int]] = mapped_column(Integer)

    file: Mapped["File"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("file_id", "ord", name="uq_chunks_file_ord"),
        Index("idx_chunks_file", "file_id"),
    )


class Enrichment(Base):
    __tablename__ = "enrichments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    chunk_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("chunks.id", ondelete="CASCADE")
    )
    file_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("files.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    file: Mapped[Optional["File"]] = relationship(back_populates="enrichments")

    __table_args__ = (
        CheckConstraint(
            "kind IN ('summary','person','date','task','category','sentiment','risk','commitment')",
            name="ck_enrichments_kind",
        ),
        Index("idx_enrich_kind", "kind"),
        Index("idx_enrich_file", "file_id"),
        Index("idx_enrich_chunk", "chunk_id"),
    )


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    file_id: Mapped[str] = mapped_column(
        String, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("chunks.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    kind: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[Optional[float]] = mapped_column()

    file: Mapped["File"] = relationship(back_populates="timeline_events")

    __table_args__ = (
        Index("idx_timeline_dt", "occurred_at"),
        Index("idx_timeline_kind", "kind"),
    )


class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    asked_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)
    cited_chunk_ids: Mapped[Optional[str]] = mapped_column(Text)
    refused: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (Index("idx_query_log_dt", "asked_at"),)
