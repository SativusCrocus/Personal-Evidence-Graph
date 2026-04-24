'use client';

import * as React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { api, type EvidenceDetail } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { EvidenceCard } from '@/components/evidence-card';
import { EvidencePreview } from '@/components/evidence-preview';

export default function EvidenceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;
  const [data, setData] = React.useState<EvidenceDetail | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!id) return;
    api.evidence(id).then(setData).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <div className="text-danger text-sm">{error}</div>;
  if (!data) return <div className="text-muted-fg flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading evidence…</div>;

  const enrich = data.enrichments;
  const people = enrich.filter((e) => e.kind === 'person').map((e) => e.value?.name).filter(Boolean);
  const dates = enrich.filter((e) => e.kind === 'date');
  const tasks = enrich.filter((e) => e.kind === 'task');
  const summary = enrich.find((e) => e.kind === 'summary')?.value?.text;
  const category = enrich.find((e) => e.kind === 'category')?.value?.name;
  const sentiment = enrich.find((e) => e.kind === 'sentiment')?.value?.label;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => router.back()} className="gap-1.5">
          <ArrowLeft className="h-3.5 w-3.5" /> Back
        </Button>
        <div className="ml-auto flex gap-2 items-center text-xs text-muted-fg">
          <Badge variant="accent">{data.file.source_type}</Badge>
          <span>{data.file.display_name}</span>
        </div>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-5">
        <div className="space-y-4">
          <EvidenceCard chunk={data.chunk} file={data.file} />

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

          {data.neighbors.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs uppercase tracking-wider text-muted-fg">Surrounding context</h3>
              {data.neighbors.map((n) => <EvidenceCard key={n.id} chunk={n} file={data.file} />)}
            </div>
          )}
        </div>

        <EvidencePreview file={data.file} ts_start_ms={data.chunk.ts_start_ms} />
      </div>
    </div>
  );
}
