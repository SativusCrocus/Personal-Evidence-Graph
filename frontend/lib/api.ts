/**
 * Typed client for the Personal Evidence Graph backend.
 *
 * All paths go through Next's /api/* rewrite to the FastAPI server.
 *
 * When the real backend is unreachable (which is the case for the public
 * Vercel preview, since the backend is local-only by design), every call
 * transparently falls back to a seeded demo dataset under lib/demo/.
 * The demo flag is sticky once set, surfaced via subscribeDemoMode() so
 * the Topbar can render a "Demo mode" banner.
 */

const BASE = '/api';

// ───────────────────────── domain types ─────────────────────────

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

/**
 * Operational telemetry surfaced by the dashboard. The backend may not yet
 * compute every field; the demo fixture fills them in deterministically so
 * the UI can be validated end-to-end.
 */
export interface IndexHealth {
  total_files: number;
  total_chunks: number;
  total_claims: number;
  total_obligations: number;
  total_contradictions: number;
  failed_files: number;
  ocr_backlog: number;
  embedding_queue_depth: number;
  last_ingest_at: string | null;
  last_query_at: string | null;
  last_llm_call_at: string | null;
  index_age_seconds: number | null;
  db_bytes: number;
  vector_dim: number;
}

// New domain types — designed in the demo layer first, will land in the
// backend when the claim/contradiction/obligation engines are built.

export type ClaimStatus = 'supported' | 'contradicted' | 'uncertain' | 'refused';

export interface Claim {
  id: string;
  text: string;
  status: ClaimStatus;
  confidence: number;
  source_chunk_id: string;
  source_file_id: string;
  source_excerpt: string;
  source_dt: string | null;
  contradiction_id?: string;
  obligation_id?: string;
}

export type ContradictionSeverity = 'low' | 'medium' | 'high';

export interface Contradiction {
  id: string;
  topic: string;
  summary: string;
  severity: ContradictionSeverity;
  detected_at: string;
  claim_ids: string[];
  related_chunk_ids: string[];
}

export type ObligationDirection = 'incoming' | 'outgoing';
export type ObligationStatus = 'open' | 'overdue' | 'completed' | 'cancelled';

export interface Obligation {
  id: string;
  text: string;
  counterparty: string;
  direction: ObligationDirection;
  due_at: string;
  status: ObligationStatus;
  claim_id: string;
  source_chunk_id: string;
  source_file_id: string;
  source_excerpt: string;
}

export type PipelineStage =
  | 'received' | 'hashed' | 'extracted' | 'chunked' | 'embedded' | 'indexed' | 'queryable';
export type PipelineStatus = 'success' | 'failed' | 'retried';

export interface PipelineEvent {
  id: string;
  file_id: string;
  stage: PipelineStage;
  status: PipelineStatus;
  at: string;
  message?: string;
}

// ───────────────────────── demo-mode plumbing ─────────────────────────

// Force demo mode only in production builds — local dev should always try
// the real backend first, regardless of any leaked env var. This protects
// users who ran `vercel env pull` from getting stuck in demo mode locally.
const FORCED_DEMO =
  typeof process !== 'undefined'
  && process.env.NEXT_PUBLIC_DEMO_MODE === '1'
  && process.env.NODE_ENV === 'production';

let isDemo = FORCED_DEMO;
let probed = FORCED_DEMO;
const demoListeners = new Set<(on: boolean) => void>();

function setDemo(on: boolean) {
  if (isDemo === on) return;
  isDemo = on;
  demoListeners.forEach((fn) => fn(on));
}

export function isDemoMode(): boolean {
  return isDemo;
}

export function subscribeDemoMode(fn: (on: boolean) => void): () => void {
  demoListeners.add(fn);
  fn(isDemo);
  return () => demoListeners.delete(fn);
}

/**
 * Manually exit demo mode and probe the backend again. Used by the demo
 * banner's "Try local backend" button. If the probe succeeds, demo mode
 * stays off; if it fails, the banner re-appears.
 */
export async function retryBackendProbe(): Promise<{ ok: boolean; error?: string }> {
  // Reset state so withDemo() will actually try the real fetch.
  setDemo(false);
  probed = false;
  try {
    const r = await fetchWithTimeout(`${BASE}/health`, { cache: 'no-store' }, 8000);
    if (!r.ok) {
      setDemo(true);
      probed = true;
      return { ok: false, error: `${r.status} ${r.statusText}` };
    }
    probed = true;
    return { ok: true };
  } catch (e) {
    setDemo(true);
    probed = true;
    return { ok: false, error: e instanceof Error ? e.message : 'request failed' };
  }
}

// 8s gives Next.js dev server enough time to compile the /api/* rewrite
// on the very first request. Production builds compile rewrites ahead of
// time so this cushion is essentially free.
const PROBE_TIMEOUT_MS = 8000;

async function fetchWithTimeout(input: string, init?: RequestInit, ms = PROBE_TIMEOUT_MS): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(input, { ...init, signal: ctrl.signal });
  } finally {
    clearTimeout(t);
  }
}

/** Race the real call against demo fallback. Sticky once demo is detected. */
async function withDemo<T>(
  real: () => Promise<T>,
  demo: () => T | Promise<T>,
): Promise<T> {
  if (isDemo) return demo();
  try {
    const out = await real();
    probed = true;
    return out;
  } catch {
    probed = true;
    setDemo(true);
    return demo();
  }
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

// ───────────────────────── public API ─────────────────────────

export const api = {
  async health(): Promise<Health> {
    return withDemo(
      async () => jsonOrThrow<Health>(await fetchWithTimeout(`${BASE}/health`, { cache: 'no-store' })),
      async () => (await import('./demo/fixtures')).health,
    );
  },

  async ingestFile(file: File): Promise<IngestResponse> {
    return withDemo(
      async () => {
        const fd = new FormData();
        fd.append('upload', file);
        return jsonOrThrow<IngestResponse>(await fetchWithTimeout(`${BASE}/ingest/file`, { method: 'POST', body: fd }, 8000));
      },
      async () => (await import('./demo/fixtures')).fakeIngest(file.name),
    );
  },

  async ingestFolder(path: string, recursive = true): Promise<IngestResponse[]> {
    return withDemo(
      async () => jsonOrThrow<IngestResponse[]>(await fetchWithTimeout(`${BASE}/ingest/folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, recursive }),
      })),
      async () => {
        const fx = await import('./demo/fixtures');
        return [fx.fakeIngest(`folder:${path}`)];
      },
    );
  },

  async ingestClipboard(text: string, source?: string): Promise<IngestResponse> {
    return withDemo(
      async () => jsonOrThrow<IngestResponse>(await fetchWithTimeout(`${BASE}/ingest/clipboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, source }),
      })),
      async () => (await import('./demo/fixtures')).fakeIngest(source ?? 'clipboard'),
    );
  },

  async query(question: string, opts?: {
    k?: number; source_types?: SourceType[]; date_from?: string; date_to?: string;
  }): Promise<AnswerResponse> {
    return withDemo(
      async () => jsonOrThrow<AnswerResponse>(await fetchWithTimeout(`${BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, ...(opts || {}) }),
      }, 6000)),
      async () => {
        const fx = await import('./demo/fixtures');
        // Slight delay so the loading state is visible in demo mode.
        await new Promise((r) => setTimeout(r, 320));
        return fx.answerForQuestion(question);
      },
    );
  },

  async timeline(opts?: { from?: string; to?: string; kind?: string; q?: string }): Promise<TimelineEvent[]> {
    return withDemo(
      async () => {
        const p = new URLSearchParams();
        if (opts?.from) p.set('from', opts.from);
        if (opts?.to) p.set('to', opts.to);
        if (opts?.kind) p.set('kind', opts.kind);
        if (opts?.q) p.set('q', opts.q);
        p.set('limit', '500');
        return jsonOrThrow<TimelineEvent[]>(await fetchWithTimeout(`${BASE}/timeline?${p.toString()}`, { cache: 'no-store' }));
      },
      async () => {
        const fx = await import('./demo/fixtures');
        let rows = fx.timeline.slice();
        if (opts?.from) rows = rows.filter((e) => e.occurred_at >= opts.from!);
        if (opts?.to) rows = rows.filter((e) => e.occurred_at <= opts.to!);
        if (opts?.kind) rows = rows.filter((e) => e.kind === opts.kind);
        if (opts?.q) {
          const q = opts.q.toLowerCase();
          rows = rows.filter((e) =>
            e.title.toLowerCase().includes(q) || (e.description ?? '').toLowerCase().includes(q),
          );
        }
        rows.sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1));
        return rows;
      },
    );
  },

  async evidence(chunkId: string): Promise<EvidenceDetail> {
    return withDemo(
      async () => jsonOrThrow<EvidenceDetail>(await fetchWithTimeout(`${BASE}/evidence/${encodeURIComponent(chunkId)}`, { cache: 'no-store' })),
      async () => {
        const fx = await import('./demo/fixtures');
        const ev = fx.evidenceFor(chunkId);
        if (!ev) throw new Error(`Chunk ${chunkId} not in demo dataset`);
        return ev;
      },
    );
  },

  fileRawUrl(fileId: string): string {
    return `${BASE}/evidence/file/${encodeURIComponent(fileId)}/raw`;
  },

  async listFiles(opts?: { status?: string; source_type?: string; q?: string }): Promise<FileSummary[]> {
    return withDemo(
      async () => {
        const p = new URLSearchParams();
        if (opts?.status) p.set('status', opts.status);
        if (opts?.source_type) p.set('source_type', opts.source_type);
        if (opts?.q) p.set('q', opts.q);
        return jsonOrThrow<FileSummary[]>(await fetchWithTimeout(`${BASE}/files?${p.toString()}`, { cache: 'no-store' }));
      },
      async () => {
        const fx = await import('./demo/fixtures');
        let rows = fx.files.slice();
        if (opts?.status) rows = rows.filter((f) => f.status === opts.status);
        if (opts?.source_type) rows = rows.filter((f) => f.source_type === opts.source_type);
        if (opts?.q) {
          const q = opts.q.toLowerCase();
          rows = rows.filter((f) => f.display_name.toLowerCase().includes(q));
        }
        return rows;
      },
    );
  },

  async deleteFile(fileId: string): Promise<{ deleted: boolean }> {
    return withDemo(
      async () => jsonOrThrow<{ deleted: boolean }>(await fetchWithTimeout(`${BASE}/files/${encodeURIComponent(fileId)}`, { method: 'DELETE' })),
      async () => ({ deleted: true }),
    );
  },

  async stats(): Promise<Stats> {
    return withDemo(
      async () => jsonOrThrow<Stats>(await fetchWithTimeout(`${BASE}/files/_/stats`, { cache: 'no-store' })),
      async () => (await import('./demo/fixtures')).stats,
    );
  },

  async reindex(): Promise<{ queued: boolean }> {
    return withDemo(
      async () => jsonOrThrow<{ queued: boolean }>(await fetchWithTimeout(`${BASE}/reindex`, { method: 'POST' })),
      async () => ({ queued: true }),
    );
  },

  // ───────── new endpoints (demo-only until the backend ships them) ─────────

  async claims(opts?: { status?: string; file_id?: string; chunk_id?: string }): Promise<Claim[]> {
    return withDemo(
      async () => {
        const p = new URLSearchParams();
        if (opts?.status) p.set('status', opts.status);
        if (opts?.file_id) p.set('file_id', opts.file_id);
        if (opts?.chunk_id) p.set('chunk_id', opts.chunk_id);
        const qs = p.toString();
        return jsonOrThrow<Claim[]>(await fetchWithTimeout(
          `${BASE}/claims${qs ? `?${qs}` : ''}`,
          { cache: 'no-store' },
        ));
      },
      async () => {
        const all = (await import('./demo/fixtures')).claims;
        return all.filter((c) =>
          (!opts?.status || c.status === opts.status) &&
          (!opts?.file_id || c.source_file_id === opts.file_id) &&
          (!opts?.chunk_id || c.source_chunk_id === opts.chunk_id),
        );
      },
    );
  },

  async contradictions(): Promise<Contradiction[]> {
    return withDemo(
      async () => jsonOrThrow<Contradiction[]>(await fetchWithTimeout(`${BASE}/contradictions`, { cache: 'no-store' })),
      async () => (await import('./demo/fixtures')).contradictions,
    );
  },

  async obligations(): Promise<Obligation[]> {
    return withDemo(
      async () => jsonOrThrow<Obligation[]>(await fetchWithTimeout(`${BASE}/obligations`, { cache: 'no-store' })),
      async () => (await import('./demo/fixtures')).obligations,
    );
  },

  async pipelineEvents(): Promise<PipelineEvent[]> {
    return withDemo(
      async () => jsonOrThrow<PipelineEvent[]>(await fetchWithTimeout(`${BASE}/pipeline/events`, { cache: 'no-store' })),
      async () => (await import('./demo/fixtures')).pipelineEvents,
    );
  },

  async indexHealth(): Promise<IndexHealth> {
    return withDemo(
      async () => jsonOrThrow<IndexHealth>(await fetchWithTimeout(`${BASE}/health/index`, { cache: 'no-store' })),
      async () => (await import('./demo/fixtures')).indexHealth(),
    );
  },
};

// Useful for the dashboard to know whether we already probed.
export function hasProbedBackend(): boolean {
  return probed;
}
