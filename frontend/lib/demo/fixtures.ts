/**
 * Seeded demo dataset for the Personal Evidence Graph.
 *
 * Story: a small-business owner uses Sequoia Print Co as a vendor.
 * The system has ingested the master agreement, two monthly invoices, a
 * voice memo from a vendor call, and a scanned shipping receipt. Two of the
 * facts in the corpus contradict each other (invoice total changed); one
 * obligation (delivery deadline) is now past due.
 *
 * The dataset doubles as the design spec for the eventual real backend.
 */

import type {
  AnswerResponse,
  ChunkOut,
  Citation,
  EvidenceDetail,
  FileSummary,
  Health,
  IngestResponse,
  Stats,
  TimelineEvent,
} from '@/lib/api';
import type {
  Claim,
  Contradiction,
  Obligation,
  PipelineEvent,
  PipelineStage,
  PipelineStatus,
} from '@/lib/api';

const NOW = '2026-04-24T15:30:00Z';

// ───────────────────────── files ─────────────────────────

export const files: FileSummary[] = [
  {
    id: 'f_master_agreement',
    display_name: 'sequoia-master-agreement.pdf',
    path: '/Users/owner/Documents/contracts/sequoia-master-agreement.pdf',
    source_type: 'pdf',
    status: 'indexed',
    bytes: 184_320,
    ingested_at: '2026-02-12T18:04:00Z',
    source_dt: '2026-02-12T00:00:00Z',
    chunk_count: 3,
  },
  {
    id: 'f_invoice_march',
    display_name: 'sequoia-invoice-march.pdf',
    path: '/Users/owner/Documents/invoices/sequoia-invoice-march.pdf',
    source_type: 'pdf',
    status: 'indexed',
    bytes: 41_988,
    ingested_at: '2026-04-01T09:11:00Z',
    source_dt: '2026-03-31T00:00:00Z',
    chunk_count: 2,
  },
  {
    id: 'f_invoice_april',
    display_name: 'sequoia-invoice-april.pdf',
    path: '/Users/owner/Documents/invoices/sequoia-invoice-april.pdf',
    source_type: 'pdf',
    status: 'indexed',
    bytes: 42_402,
    ingested_at: '2026-04-22T08:46:00Z',
    source_dt: '2026-04-21T00:00:00Z',
    chunk_count: 2,
  },
  {
    id: 'f_voicememo_call',
    display_name: 'vendor-call-2026-04-08.m4a',
    path: '/Users/owner/Documents/voice/vendor-call-2026-04-08.m4a',
    source_type: 'audio',
    status: 'indexed',
    bytes: 2_412_113,
    ingested_at: '2026-04-08T16:33:00Z',
    source_dt: '2026-04-08T16:14:00Z',
    chunk_count: 2,
  },
  {
    id: 'f_receipt_shipping',
    display_name: 'ups-receipt-2026-04-19.jpg',
    path: '/Users/owner/Documents/receipts/ups-receipt-2026-04-19.jpg',
    source_type: 'image',
    status: 'indexed',
    bytes: 612_440,
    ingested_at: '2026-04-19T11:02:00Z',
    source_dt: '2026-04-19T00:00:00Z',
    chunk_count: 1,
  },
];

// ───────────────────────── chunks ─────────────────────────

export const chunks: ChunkOut[] = [
  // master agreement
  {
    id: 'c_master_1',
    ord: 0,
    page: 1,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'MASTER SERVICES AGREEMENT — Sequoia Print Co. and Owner (the "Customer"). ' +
      'This agreement is entered into on February 12, 2026 and governs all production work ' +
      'requested by the Customer through the term ending February 11, 2027.',
  },
  {
    id: 'c_master_2',
    ord: 1,
    page: 2,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'Section 4.2 — Pricing. Per-unit pricing for standard offset runs shall be locked at ' +
      'the rates in Schedule A for the duration of the agreement. Any change to the rate ' +
      'card requires 30 days written notice to the Customer.',
  },
  {
    id: 'c_master_3',
    ord: 2,
    page: 4,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'Schedule A: Standard Q1/Q2 production — $4,500 base per monthly run, inclusive of setup, ' +
      'plates, and one round of revisions. Rush surcharges itemized separately.',
  },

  // march invoice
  {
    id: 'c_inv_mar_1',
    ord: 0,
    page: 1,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'INVOICE #2026-031 — Sequoia Print Co. Bill date: March 31, 2026. ' +
      'Standard production run (Schedule A). Subtotal: $4,500.00. Tax: $0.00. Total due: $4,500.00. ' +
      'Net 30, due April 30, 2026.',
  },
  {
    id: 'c_inv_mar_2',
    ord: 1,
    page: 1,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'Line items: 1× monthly offset run, 2,000 units, 4-color, includes plates and one revision. ' +
      'Per master agreement Schedule A.',
  },

  // april invoice — different total!
  {
    id: 'c_inv_apr_1',
    ord: 0,
    page: 1,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'INVOICE #2026-049 — Sequoia Print Co. Bill date: April 21, 2026. ' +
      'Standard production run. Subtotal: $5,200.00. Tax: $0.00. Total due: $5,200.00. ' +
      'Net 30, due May 21, 2026.',
  },
  {
    id: 'c_inv_apr_2',
    ord: 1,
    page: 1,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'Line items: 1× monthly offset run, 2,000 units, 4-color, includes plates and one revision. ' +
      'Per master agreement Schedule A. (No itemized rush surcharge listed.)',
  },

  // voice memo
  {
    id: 'c_voice_1',
    ord: 0,
    page: null,
    ts_start_ms: 0,
    ts_end_ms: 47_000,
    text:
      "Owner: Just to confirm — you said the April run will be ready by the 15th, right? " +
      "Sequoia rep: Yes, absolutely. We'll have everything packed and out the door by April 15th. " +
      "You'll see a UPS tracking number that day.",
  },
  {
    id: 'c_voice_2',
    ord: 1,
    page: null,
    ts_start_ms: 47_000,
    ts_end_ms: 92_000,
    text:
      "Owner: And pricing is the same as last month? Sequoia rep: Same Schedule A pricing, yep. " +
      "I'll send the invoice the day we ship.",
  },

  // shipping receipt (OCR'd)
  {
    id: 'c_receipt_1',
    ord: 0,
    page: null,
    ts_start_ms: null,
    ts_end_ms: null,
    text:
      'UPS Ground Receipt — Tracking 1Z999AA10123456784. Ship date 04/19/2026. ' +
      'Pickup from Sequoia Print Co, 412 Industrial Way. Total charge $87.40. ' +
      'Delivery est. 04/22/2026.',
  },
];

export const chunksByFile: Record<string, ChunkOut[]> = {
  f_master_agreement: chunks.filter((c) => c.id.startsWith('c_master')),
  f_invoice_march: chunks.filter((c) => c.id.startsWith('c_inv_mar')),
  f_invoice_april: chunks.filter((c) => c.id.startsWith('c_inv_apr')),
  f_voicememo_call: chunks.filter((c) => c.id.startsWith('c_voice')),
  f_receipt_shipping: chunks.filter((c) => c.id.startsWith('c_receipt')),
};

// Reverse: chunk -> file
export const fileForChunk: Record<string, string> = Object.fromEntries(
  Object.entries(chunksByFile).flatMap(([fid, cs]) => cs.map((c) => [c.id, fid] as const)),
);

// ───────────────────────── claims ─────────────────────────

export const claims: Claim[] = [
  {
    id: 'cl_delivery_april_15',
    text: 'Sequoia Print Co will deliver the April production run by April 15, 2026.',
    status: 'supported',
    confidence: 0.92,
    source_chunk_id: 'c_voice_1',
    source_file_id: 'f_voicememo_call',
    source_excerpt:
      "We'll have everything packed and out the door by April 15th.",
    source_dt: '2026-04-08T16:14:00Z',
    obligation_id: 'ob_delivery_april_15',
  },
  {
    id: 'cl_invoice_march_total',
    text: 'March invoice total is $4,500.00.',
    status: 'contradicted',
    confidence: 0.99,
    source_chunk_id: 'c_inv_mar_1',
    source_file_id: 'f_invoice_march',
    source_excerpt: 'Subtotal: $4,500.00. Tax: $0.00. Total due: $4,500.00.',
    source_dt: '2026-03-31T00:00:00Z',
    contradiction_id: 'cn_invoice_total_changed',
  },
  {
    id: 'cl_invoice_april_total',
    text: 'April invoice total is $5,200.00.',
    status: 'contradicted',
    confidence: 0.99,
    source_chunk_id: 'c_inv_apr_1',
    source_file_id: 'f_invoice_april',
    source_excerpt: 'Subtotal: $5,200.00. Tax: $0.00. Total due: $5,200.00.',
    source_dt: '2026-04-21T00:00:00Z',
    contradiction_id: 'cn_invoice_total_changed',
  },
  {
    id: 'cl_master_signed',
    text: 'Master Services Agreement with Sequoia Print Co was signed February 12, 2026.',
    status: 'supported',
    confidence: 0.97,
    source_chunk_id: 'c_master_1',
    source_file_id: 'f_master_agreement',
    source_excerpt:
      'This agreement is entered into on February 12, 2026 and governs all production work',
    source_dt: '2026-02-12T00:00:00Z',
  },
  {
    id: 'cl_shipping_total',
    text: 'Shipping for the April production cost $87.40 (UPS Ground).',
    status: 'supported',
    confidence: 0.84,
    source_chunk_id: 'c_receipt_1',
    source_file_id: 'f_receipt_shipping',
    source_excerpt: 'Total charge $87.40.',
    source_dt: '2026-04-19T00:00:00Z',
  },
];

export const claimsByChunk: Record<string, Claim[]> = claims.reduce<Record<string, Claim[]>>(
  (acc, cl) => {
    (acc[cl.source_chunk_id] ||= []).push(cl);
    return acc;
  },
  {},
);

// ───────────────────────── contradictions ─────────────────────────

export const contradictions: Contradiction[] = [
  {
    id: 'cn_invoice_total_changed',
    topic: 'Monthly invoice total',
    summary:
      'Sequoia Print Co billed $4,500 in March and $5,200 in April for an identical line ' +
      'item (1× monthly offset run, 2,000 units, 4-color, Schedule A). The master agreement ' +
      'requires 30 days written notice for any rate change — no such notice is on file.',
    severity: 'high',
    detected_at: '2026-04-22T08:46:14Z',
    claim_ids: ['cl_invoice_march_total', 'cl_invoice_april_total'],
    related_chunk_ids: ['c_master_2', 'c_master_3'],
  },
];

// ───────────────────────── obligations ─────────────────────────

export const obligations: Obligation[] = [
  {
    id: 'ob_delivery_april_15',
    text: 'Sequoia Print Co to deliver April production run',
    counterparty: 'Sequoia Print Co',
    direction: 'incoming',
    due_at: '2026-04-15T23:59:00Z',
    status: 'overdue',
    claim_id: 'cl_delivery_april_15',
    source_chunk_id: 'c_voice_1',
    source_file_id: 'f_voicememo_call',
    source_excerpt:
      "We'll have everything packed and out the door by April 15th.",
  },
];

// ───────────────────────── pipeline events ─────────────────────────

const allStages: PipelineStage[] = [
  'received', 'hashed', 'extracted', 'chunked', 'embedded', 'indexed', 'queryable',
];

function makePipeline(
  fileId: string,
  start: string,
  opts: { stuck?: PipelineStage; failedRetries?: { stage: PipelineStage; error: string }[] } = {},
): PipelineEvent[] {
  const startMs = new Date(start).getTime();
  const out: PipelineEvent[] = [];
  let cursor = startMs;
  const stop = opts.stuck;
  for (const stage of allStages) {
    cursor += 800 + Math.random() * 1200;
    if (stop && allStages.indexOf(stage) > allStages.indexOf(stop)) break;
    const failed = opts.failedRetries?.find((f) => f.stage === stage);
    if (failed) {
      out.push({
        id: `${fileId}_${stage}_failed`,
        file_id: fileId,
        stage,
        status: 'failed',
        at: new Date(cursor).toISOString(),
        message: failed.error,
      });
      cursor += 1500;
      out.push({
        id: `${fileId}_${stage}_retried`,
        file_id: fileId,
        stage,
        status: 'retried',
        at: new Date(cursor).toISOString(),
        message: 'Retried with PaddleOCR fallback',
      });
      cursor += 1200;
    }
    out.push({
      id: `${fileId}_${stage}`,
      file_id: fileId,
      stage,
      status: 'success',
      at: new Date(cursor).toISOString(),
    });
  }
  return out;
}

export const pipelineEvents: PipelineEvent[] = [
  ...makePipeline('f_master_agreement', '2026-02-12T18:04:00Z'),
  ...makePipeline('f_invoice_march', '2026-04-01T09:11:00Z'),
  ...makePipeline('f_invoice_april', '2026-04-22T08:46:00Z'),
  ...makePipeline('f_voicememo_call', '2026-04-08T16:33:00Z'),
  ...makePipeline('f_receipt_shipping', '2026-04-19T11:02:00Z', {
    failedRetries: [
      { stage: 'extracted', error: 'Tesseract: low-confidence regions, 0.41 mean conf' },
    ],
  }),
];

export const pipelineByFile: Record<string, PipelineEvent[]> = pipelineEvents.reduce<
  Record<string, PipelineEvent[]>
>((acc, e) => {
  (acc[e.file_id] ||= []).push(e);
  return acc;
}, {});

export function pipelineStateFor(fileId: string): {
  stage: PipelineStage;
  status: PipelineStatus;
  reachedAt: string;
} {
  const evs = pipelineByFile[fileId] || [];
  const last = evs[evs.length - 1];
  if (!last) return { stage: 'received', status: 'success', reachedAt: NOW };
  return { stage: last.stage, status: last.status, reachedAt: last.at };
}

// ───────────────────────── timeline ─────────────────────────

export const timeline: TimelineEvent[] = [
  {
    id: 't_master_signed',
    occurred_at: '2026-02-12T00:00:00Z',
    title: 'Master Services Agreement signed with Sequoia Print Co',
    description: 'Annual MSA, term ending Feb 11 2027. Schedule A pricing locked.',
    kind: 'agreement',
    file_id: 'f_master_agreement',
    chunk_id: 'c_master_1',
    file_name: 'sequoia-master-agreement.pdf',
    source_type: 'pdf',
    confidence: 0.97,
  },
  {
    id: 't_invoice_march',
    occurred_at: '2026-03-31T00:00:00Z',
    title: 'Sequoia invoice #2026-031 — $4,500.00',
    description: 'Standard monthly run, Schedule A pricing.',
    kind: 'invoice',
    file_id: 'f_invoice_march',
    chunk_id: 'c_inv_mar_1',
    file_name: 'sequoia-invoice-march.pdf',
    source_type: 'pdf',
    confidence: 0.99,
  },
  {
    id: 't_call_april',
    occurred_at: '2026-04-08T16:14:00Z',
    title: 'Phone call with Sequoia — delivery confirmed for April 15',
    description: 'Vendor confirms April production ships by 4/15. Same Schedule A pricing.',
    kind: 'call',
    file_id: 'f_voicememo_call',
    chunk_id: 'c_voice_1',
    file_name: 'vendor-call-2026-04-08.m4a',
    source_type: 'audio',
    confidence: 0.92,
  },
  {
    id: 't_deadline_april_15',
    occurred_at: '2026-04-15T23:59:00Z',
    title: 'Deadline — April production run delivery',
    description: 'Promised by Sequoia rep on the 04/08 call. Linked obligation.',
    kind: 'deadline',
    file_id: 'f_voicememo_call',
    chunk_id: 'c_voice_1',
    file_name: 'vendor-call-2026-04-08.m4a',
    source_type: 'audio',
    confidence: 0.92,
  },
  {
    id: 't_shipping',
    occurred_at: '2026-04-19T00:00:00Z',
    title: 'UPS pickup from Sequoia — $87.40',
    description: 'Tracking 1Z999AA10123456784. Shipped 4 days after promised delivery.',
    kind: 'shipment',
    file_id: 'f_receipt_shipping',
    chunk_id: 'c_receipt_1',
    file_name: 'ups-receipt-2026-04-19.jpg',
    source_type: 'image',
    confidence: 0.84,
  },
  {
    id: 't_invoice_april',
    occurred_at: '2026-04-21T00:00:00Z',
    title: 'Sequoia invoice #2026-049 — $5,200.00',
    description: 'Same line items as March. Total increased $700. No 30-day notice on file.',
    kind: 'invoice',
    file_id: 'f_invoice_april',
    chunk_id: 'c_inv_apr_1',
    file_name: 'sequoia-invoice-april.pdf',
    source_type: 'pdf',
    confidence: 0.99,
  },
];

// ───────────────────────── health & stats ─────────────────────────

export const health: Health = {
  ok: true,
  version: '0.1.0-demo',
  db: true,
  chroma: true,
  ollama: true,
  embed_model: 'bge-small-en-v1.5',
  llm_model: 'llama3.1:8b (demo)',
};

export const stats: Stats = {
  files: files.length,
  chunks: chunks.length,
  timeline_events: timeline.length,
  queries: 12,
  refused: 3,
  by_source_type: {
    pdf: 3,
    audio: 1,
    image: 1,
  },
};

// ───────────────────────── query handler ─────────────────────────

const REFUSAL = 'No supporting evidence found.';

interface ScriptedAnswer {
  match: RegExp;
  answer: string;
  confidence: number;
  citationChunkIds: string[];
}

const scripted: ScriptedAnswer[] = [
  {
    match: /(deliver|ship|when.*(?:april|due)|deadline|by the 15th|april 15)/i,
    answer:
      "Sequoia Print Co confirmed they would deliver the April production run by April 15, 2026. " +
      "On the April 8 phone call, the rep said: \"We'll have everything packed and out the door by April 15th.\" " +
      "Tracking shows the UPS pickup did not happen until April 19, so the obligation is overdue.",
    confidence: 0.91,
    citationChunkIds: ['c_voice_1', 'c_receipt_1'],
  },
  {
    match: /(invoice|price|cost|how much|\$|total|billed|charge)/i,
    answer:
      "There is a contradiction in Sequoia's billing. " +
      "The March invoice (#2026-031) totalled $4,500.00 for the standard monthly run. " +
      "The April invoice (#2026-049) totals $5,200.00 — a $700 increase — for an identical line item. " +
      "The Master Services Agreement requires 30 days written notice for any rate change, and no such notice is on file.",
    confidence: 0.94,
    citationChunkIds: ['c_inv_mar_1', 'c_inv_apr_1', 'c_master_2'],
  },
  {
    match: /(agreement|contract|signed|master|terms)/i,
    answer:
      "The Master Services Agreement with Sequoia Print Co was signed on February 12, 2026, with a term ending February 11, 2027. " +
      "Section 4.2 locks per-unit pricing to Schedule A and requires 30 days written notice for any rate change.",
    confidence: 0.96,
    citationChunkIds: ['c_master_1', 'c_master_2'],
  },
  {
    match: /(shipping|ups|tracking|receipt)/i,
    answer:
      "Shipping for the April production was $87.40 via UPS Ground. The receipt shows pickup from Sequoia Print Co on April 19, 2026, with tracking 1Z999AA10123456784.",
    confidence: 0.88,
    citationChunkIds: ['c_receipt_1'],
  },
];

function citationFor(chunkId: string, score: number): Citation {
  const chunk = chunks.find((c) => c.id === chunkId)!;
  const fileId = fileForChunk[chunkId];
  const file = files.find((f) => f.id === fileId)!;
  return {
    chunk_id: chunk.id,
    file_id: file.id,
    file_name: file.display_name,
    file_path: file.path,
    source_type: file.source_type,
    source_dt: file.source_dt,
    page: chunk.page,
    ts_start_ms: chunk.ts_start_ms,
    ts_end_ms: chunk.ts_end_ms,
    excerpt: chunk.text.slice(0, 220) + (chunk.text.length > 220 ? '…' : ''),
    score,
  };
}

export function answerForQuestion(question: string): AnswerResponse {
  const t0 = Date.now();
  const hit = scripted.find((s) => s.match.test(question));
  // Simulated latency so the loading spinner feels real.
  const latency_ms = 240 + Math.floor(Math.random() * 220);
  if (!hit) {
    return {
      answer: REFUSAL,
      citations: [],
      confidence: 0,
      refused: true,
      latency_ms,
    };
  }
  const citations = hit.citationChunkIds.map((id, i) => citationFor(id, 0.82 - i * 0.06));
  void t0;
  return {
    answer: hit.answer,
    citations,
    confidence: hit.confidence,
    refused: false,
    latency_ms,
  };
}

// ───────────────────────── ingest stub ─────────────────────────

export function fakeIngest(name: string): IngestResponse {
  return {
    file_id: `demo_${Date.now().toString(36)}`,
    sha256: 'demo:' + name,
    status: 'indexed',
    duplicate: false,
  };
}

// ───────────────────────── evidence detail ─────────────────────────

export function evidenceFor(chunkId: string): EvidenceDetail | null {
  const chunk = chunks.find((c) => c.id === chunkId);
  if (!chunk) return null;
  const fileId = fileForChunk[chunkId];
  const file = files.find((f) => f.id === fileId)!;
  const neighbors = (chunksByFile[fileId] || []).filter((c) => c.id !== chunkId).slice(0, 2);
  const cl = (claimsByChunk[chunkId] || [])[0];
  const enrichments: EvidenceDetail['enrichments'] = [];
  if (cl) {
    enrichments.push({
      kind: 'summary',
      value: { text: cl.text },
      confidence: cl.confidence,
    });
  }
  if (file.source_type === 'audio') {
    enrichments.push({ kind: 'category', value: { name: 'phone call' }, confidence: 0.9 });
    enrichments.push({ kind: 'person', value: { name: 'Sequoia rep' }, confidence: 0.7 });
  }
  if (file.id === 'f_invoice_march' || file.id === 'f_invoice_april') {
    enrichments.push({ kind: 'category', value: { name: 'invoice' }, confidence: 0.95 });
  }
  return {
    chunk,
    file,
    neighbors,
    enrichments,
  };
}

// ───────────────────────── lookups ─────────────────────────

export function claimById(id: string): Claim | undefined {
  return claims.find((c) => c.id === id);
}
export function contradictionById(id: string): Contradiction | undefined {
  return contradictions.find((c) => c.id === id);
}
export function obligationById(id: string): Obligation | undefined {
  return obligations.find((o) => o.id === id);
}
