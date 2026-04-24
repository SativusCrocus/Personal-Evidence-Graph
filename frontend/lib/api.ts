/**
 * Typed client for the Personal Evidence Graph backend.
 * All paths go through Next's /api/* rewrite to the FastAPI server.
 */

const BASE = '/api';

export type SourceType =
  | 'pdf' | 'image' | 'audio' | 'text' | 'browser' | 'clipboard' | 'video' | 'other';
export type FileStatus = 'pending' | 'extracting' | 'enriching' | 'indexed' | 'failed';

export interface Health {
  ok: boolean;
  version: string;
  db: boolean;
  chroma: boolean;
  ollama: boolean;
  embed_model: string;
  llm_model: string;
}

export interface IngestResponse {
  file_id: string;
  sha256: string;
  status: FileStatus;
  duplicate: boolean;
}

export interface Citation {
  chunk_id: string;
  file_id: string;
  file_name: string;
  file_path: string;
  source_type: SourceType;
  source_dt: string | null;
  page: number | null;
  ts_start_ms: number | null;
  ts_end_ms: number | null;
  excerpt: string;
  score: number;
}

export interface AnswerResponse {
  answer: string;
  citations: Citation[];
  confidence: number;
  refused: boolean;
  latency_ms: number;
}

export interface FileSummary {
  id: string;
  display_name: string;
  path: string;
  source_type: SourceType;
  status: FileStatus;
  bytes: number;
  ingested_at: string;
  source_dt: string | null;
  chunk_count: number;
}

export interface ChunkOut {
  id: string;
  ord: number;
  text: string;
  page: number | null;
  ts_start_ms: number | null;
  ts_end_ms: number | null;
}

export interface EvidenceDetail {
  chunk: ChunkOut;
  file: FileSummary;
  neighbors: ChunkOut[];
  enrichments: Array<{ kind: string; value: any; confidence: number | null }>;
}

export interface TimelineEvent {
  id: string;
  occurred_at: string;
  title: string;
  description: string | null;
  kind: string | null;
  file_id: string;
  chunk_id: string | null;
  file_name: string;
  source_type: SourceType;
  confidence: number | null;
}

export interface Stats {
  files: number;
  chunks: number;
  timeline_events: number;
  queries: number;
  refused: number;
  by_source_type: Record<string, number>;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: string;
    try {
      const j = await res.json();
      detail = (j && (j.detail || j.error)) || res.statusText;
    } catch {
      detail = res.statusText;
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  async health(): Promise<Health> {
    return jsonOrThrow(await fetch(`${BASE}/health`, { cache: 'no-store' }));
  },

  async ingestFile(file: File): Promise<IngestResponse> {
    const fd = new FormData();
    fd.append('upload', file);
    return jsonOrThrow(await fetch(`${BASE}/ingest/file`, { method: 'POST', body: fd }));
  },

  async ingestFolder(path: string, recursive = true): Promise<IngestResponse[]> {
    return jsonOrThrow(await fetch(`${BASE}/ingest/folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, recursive }),
    }));
  },

  async ingestClipboard(text: string, source?: string): Promise<IngestResponse> {
    return jsonOrThrow(await fetch(`${BASE}/ingest/clipboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source }),
    }));
  },

  async query(question: string, opts?: {
    k?: number; source_types?: SourceType[]; date_from?: string; date_to?: string;
  }): Promise<AnswerResponse> {
    return jsonOrThrow(await fetch(`${BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, ...(opts || {}) }),
    }));
  },

  async timeline(opts?: { from?: string; to?: string; kind?: string; q?: string }): Promise<TimelineEvent[]> {
    const p = new URLSearchParams();
    if (opts?.from) p.set('from', opts.from);
    if (opts?.to) p.set('to', opts.to);
    if (opts?.kind) p.set('kind', opts.kind);
    if (opts?.q) p.set('q', opts.q);
    p.set('limit', '500');
    return jsonOrThrow(await fetch(`${BASE}/timeline?${p.toString()}`, { cache: 'no-store' }));
  },

  async evidence(chunkId: string): Promise<EvidenceDetail> {
    return jsonOrThrow(await fetch(`${BASE}/evidence/${encodeURIComponent(chunkId)}`, { cache: 'no-store' }));
  },

  fileRawUrl(fileId: string): string {
    return `${BASE}/evidence/file/${encodeURIComponent(fileId)}/raw`;
  },

  async listFiles(opts?: { status?: string; source_type?: string; q?: string }): Promise<FileSummary[]> {
    const p = new URLSearchParams();
    if (opts?.status) p.set('status', opts.status);
    if (opts?.source_type) p.set('source_type', opts.source_type);
    if (opts?.q) p.set('q', opts.q);
    return jsonOrThrow(await fetch(`${BASE}/files?${p.toString()}`, { cache: 'no-store' }));
  },

  async deleteFile(fileId: string): Promise<{ deleted: boolean }> {
    return jsonOrThrow(await fetch(`${BASE}/files/${encodeURIComponent(fileId)}`, { method: 'DELETE' }));
  },

  async stats(): Promise<Stats> {
    return jsonOrThrow(await fetch(`${BASE}/files/_/stats`, { cache: 'no-store' }));
  },

  async reindex(): Promise<{ queued: boolean }> {
    return jsonOrThrow(await fetch(`${BASE}/reindex`, { method: 'POST' }));
  },
};
