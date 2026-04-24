from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["pdf", "image", "audio", "text", "browser", "clipboard", "video", "other"]
FileStatus = Literal["pending", "extracting", "enriching", "indexed", "failed"]


class HealthStatus(BaseModel):
    ok: bool
    version: str
    db: bool
    chroma: bool
    ollama: bool
    embed_model: str
    llm_model: str


class IngestResponse(BaseModel):
    file_id: str
    sha256: str
    status: FileStatus
    duplicate: bool = False


class IngestFolderRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4096)
    recursive: bool = True


class IngestClipboardRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1_000_000)
    source: Optional[str] = Field(default=None, max_length=512)
    occurred_at: Optional[datetime] = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    k: Optional[int] = Field(default=None, ge=1, le=32)
    source_types: Optional[list[SourceType]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class Citation(BaseModel):
    chunk_id: str
    file_id: str
    file_name: str
    file_path: str
    source_type: SourceType
    source_dt: Optional[datetime] = None
    page: Optional[int] = None
    ts_start_ms: Optional[int] = None
    ts_end_ms: Optional[int] = None
    excerpt: str
    score: float


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    refused: bool = False
    latency_ms: int = 0


class FileSummary(BaseModel):
    id: str
    display_name: str
    path: str
    source_type: SourceType
    status: FileStatus
    bytes: int
    ingested_at: datetime
    source_dt: Optional[datetime] = None
    chunk_count: int = 0


class ChunkOut(BaseModel):
    id: str
    ord: int
    text: str
    page: Optional[int] = None
    ts_start_ms: Optional[int] = None
    ts_end_ms: Optional[int] = None


class EvidenceDetail(BaseModel):
    chunk: ChunkOut
    file: FileSummary
    neighbors: list[ChunkOut]
    enrichments: list[dict] = []


class TimelineEventOut(BaseModel):
    id: str
    occurred_at: datetime
    title: str
    description: Optional[str] = None
    kind: Optional[str] = None
    file_id: str
    chunk_id: Optional[str] = None
    file_name: str
    source_type: SourceType
    confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
