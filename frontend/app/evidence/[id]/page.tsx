'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Loader2, AlertTriangle, ChevronLeft, ChevronRight,
  Quote, Clock, FileText,
} from 'lucide-react';
import {
  api, type EvidenceDetail, type Claim, type Contradiction,
  type Obligation, type ChunkOut,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { EvidenceCard } from '@/components/evidence-card';
import { EvidencePreview } from '@/components/evidence-preview';
import { CopyButton } from '@/components/copy-button';
import { HighlightedText } from '@/components/highlighted-text';
import {
  ClaimStatusBadge, ContradictionCard, ObligationRow, PanelHeader,
} from '@/components/proof-panels';
import { formatTimecode } from '@/lib/utils';

export default function EvidenceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;
  const [data, setData] = React.useState<EvidenceDetail | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [claims, setClaims] = React.useState<Claim[]>([]);
  const [contradictions, setContradictions] = React.useState<Contradiction[]>([]);
  const [obligations, setObligations] = React.useState<Obligation[]>([]);

  React.useEffect(() => {
    if (!id) return;
    setError(null);
    setData(null);
    setClaims([]);
    setContradictions([]);
    setObligations([]);

    api.evidence(id).then(setData).catch((e) => setError(String(e)));
    void api.claims({ chunk_id: id }).then(async (cls) => {
      setClaims(cls);
      if (cls.length === 0) return;
      const [allCns, allObs] = await Promise.all([api.contradictions(), api.obligations()]);
      const cnIds = new Set(cls.map((c) => c.contradiction_id).filter(Boolean) as string[]);
      const obIds = new Set(cls.map((c) => c.obligation_id).filter(Boolean) as string[]);
      setContradictions(allCns.filter((c) => cnIds.has(c.id)));
      setObligations(allObs.filter((o) => obIds.has(o.id)));
    }).catch(() => { /* endpoints may be absent on older backends */ });
  }, [id]);

  if (error) return (
    <div className="rounded-md border border-danger/40 bg-danger/5 p-4 text-sm text-danger flex items-start gap-2">
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
      <span>{error}</span>
    </div>
  );
  if (!data) return (
    <div className="text-muted-fg flex items-center gap-2">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading evidence…
    </div>
  );

  const enrich = data.enrichments;
  const summary = enrich.find((e) => e.kind === 'summary')?.value?.text;
  const category = enrich.find((e) => e.kind === 'category')?.value?.name;
  const sentiment = enrich.find((e) => e.kind === 'sentiment')?.value?.label;
  const people = enrich.filter((e) => e.kind === 'person').map((e) => e.value?.name).filter(Boolean);
  const dates = enrich.filter((e) => e.kind === 'date');
  const tasks = enrich.filter((e) => e.kind === 'task');

  const highlights = claims.map((c) => c.source_excerpt);

  // Prev / next navigation: from neighbors, ordered by chunk ord.
  const ordered = [...data.neighbors, data.chunk].sort((a, b) => a.ord - b.ord);
  const idx = ordered.findIndex((c) => c.id === data.chunk.id);
  const prev = idx > 0 ? ordered[idx - 1] : null;
  const next = idx >= 0 && idx < ordered.length - 1 ? ordered[idx + 1] : null;

  // Audio: timestamp jumper.
  const isAudio = data.file.source_type === 'audio';
  const ts = data.chunk.ts_start_ms;

  return (
    <div className="space-y-5">
      {/* Top bar */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => router.back()} className="gap-1.5">
          <ArrowLeft className="h-3.5 w-3.5" /> Back
        </Button>
        <div className="ml-auto flex gap-2 items-center text-xs text-muted-fg">
          <Badge variant="accent">{data.file.source_type}</Badge>
          <span className="truncate max-w-[300px]">{data.file.display_name}</span>
          <Badge>chunk #{data.chunk.ord}</Badge>
          {data.chunk.page != null && <Badge>page {data.chunk.page}</Badge>}
          {isAudio && ts != null && (
            <Badge>
              <Clock className="h-3 w-3 mr-1 inline" />
              {formatTimecode(ts)}
            </Badge>
          )}
        </div>
      </div>

      {/* Claims grounded here (multi-claim aware) */}
      {claims.length > 0 && (
        <div className="rounded-md border border-accent/30 bg-accent/5 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Quote className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
              {claims.length === 1
                ? 'Claim grounded in this chunk'
                : `${claims.length} claims grounded in this chunk`}
            </h2>
          </div>
          <ul className="space-y-2.5">
            {claims.map((cl) => (
              <li key={cl.id} className="space-y-1.5">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium leading-snug">{cl.text}</div>
                    <div className="text-[11px] text-muted-fg italic mt-0.5">
                      “{cl.source_excerpt}”
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <ClaimStatusBadge status={cl.status} />
                    <Badge>conf {Math.round(cl.confidence * 100)}%</Badge>
                  </div>
                </div>
                <div className="flex items-center gap-1 -ml-2">
                  <CopyButton text={cl.source_excerpt} label="Copy excerpt" />
                  <CopyButton text={cl.text} label="Copy claim" />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-5">
        {/* Left column: chunk + extracted + linked items + neighbors */}
        <div className="space-y-4">
          <EvidenceCard chunk={data.chunk} file={data.file} highlights={highlights} emphasised />

          {(summary || category || sentiment || people.length || dates.length || tasks.length) && (
            <div className="rounded-md border border-border bg-elevated p-4 space-y-3">
              <h3 className="text-xs uppercase tracking-wider text-muted-fg">AI extracted</h3>
              {summary && <p className="text-sm">{summary}</p>}
              <div className="flex flex-wrap gap-1.5">
                {category && <Badge variant="accent">{category}</Badge>}
                {sentiment && <Badge>{sentiment}</Badge>}
                {people.map((p, i) => <Badge key={i}>{p}</Badge>)}
              </div>
              {dates.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[11px] uppercase text-muted-fg">Dates</div>
                  <ul className="text-sm space-y-0.5">
                    {dates.map((d, i) => (
                      <li key={i}>{d.value?.date} <span className="text-muted-fg">— {d.value?.context}</span></li>
                    ))}
                  </ul>
                </div>
              )}
              {tasks.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[11px] uppercase text-muted-fg">Tasks / commitments</div>
                  <ul className="text-sm space-y-0.5 list-disc pl-5">
                    {tasks.map((t, i) => <li key={i}>{t.value?.text}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {contradictions.length > 0 && (
            <div className="space-y-2">
              <PanelHeader title="Conflicts with another claim" count={contradictions.length} />
              <div className="space-y-2">
                {contradictions.map((c) => <ContradictionCard key={c.id} c={c} />)}
              </div>
            </div>
          )}

          {obligations.length > 0 && (
            <div className="space-y-2">
              <PanelHeader title="Obligations tracked" count={obligations.length} />
              <div className="space-y-2">
                {obligations.map((o) => <ObligationRow key={o.id} o={o} />)}
              </div>
            </div>
          )}

          {/* Prev / next navigator + surrounding context */}
          {(prev || next || data.neighbors.length > 0) && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs uppercase tracking-wider text-muted-fg">Surrounding context</h3>
                <div className="flex items-center gap-1">
                  <Button
                    asChild
                    variant="ghost"
                    size="sm"
                    disabled={!prev}
                    className="gap-1 text-xs disabled:opacity-40"
                  >
                    {prev ? (
                      <Link href={`/evidence/${encodeURIComponent(prev.id)}`}>
                        <ChevronLeft className="h-3 w-3" /> Prev #{prev.ord}
                      </Link>
                    ) : (
                      <span><ChevronLeft className="h-3 w-3" /> Prev</span>
                    )}
                  </Button>
                  <Button
                    asChild
                    variant="ghost"
                    size="sm"
                    disabled={!next}
                    className="gap-1 text-xs disabled:opacity-40"
                  >
                    {next ? (
                      <Link href={`/evidence/${encodeURIComponent(next.id)}`}>
                        Next #{next.ord} <ChevronRight className="h-3 w-3" />
                      </Link>
                    ) : (
                      <span>Next <ChevronRight className="h-3 w-3" /></span>
                    )}
                  </Button>
                </div>
              </div>
              {data.neighbors.length > 0 && (
                <div className="space-y-2">
                  {data.neighbors.map((n) => (
                    <NeighborCard key={n.id} chunk={n} fileSourceType={data.file.source_type} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right column: source preview */}
        <EvidencePreview file={data.file} ts_start_ms={data.chunk.ts_start_ms} />
      </div>
    </div>
  );
}

function NeighborCard({
  chunk, fileSourceType,
}: { chunk: ChunkOut; fileSourceType: string }) {
  const isAudio = fileSourceType === 'audio';
  const tc = chunk.ts_start_ms != null && chunk.ts_end_ms != null
    ? `${formatTimecode(chunk.ts_start_ms)} – ${formatTimecode(chunk.ts_end_ms)}`
    : null;
  return (
    <Link
      href={`/evidence/${encodeURIComponent(chunk.id)}`}
      className="block rounded-md border border-border bg-surface px-4 py-3 hover:border-accent/40 hover:bg-accent/5 transition-colors"
    >
      <div className="flex items-center gap-2 text-xs text-muted-fg mb-1">
        <FileText className="h-3 w-3" />
        <span>chunk #{chunk.ord}</span>
        {chunk.page != null && <span>· page {chunk.page}</span>}
        {tc && <span>· {tc}</span>}
        {isAudio && chunk.ts_start_ms != null && (
          <span className="ml-auto inline-flex items-center gap-1 text-accent">
            <Clock className="h-3 w-3" /> jump
          </span>
        )}
      </div>
      <HighlightedText text={chunk.text} excerpts={[]} className="text-sm text-fg/80 line-clamp-2" />
    </Link>
  );
}
