'use client';

import * as React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import {
  ArrowRight, Database, FileText, Hash, Clock, Search,
  AlertTriangle, ListChecks, GitFork, Activity,
} from 'lucide-react';
import {
  api, type Stats, type Health, type TimelineEvent, type Claim,
  type Contradiction, type Obligation, type FileSummary, type PipelineEvent,
} from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { TimelineView } from '@/components/timeline-view';
import {
  ClaimRow, ContradictionCard, ObligationRow, PipelineRow,
  PanelHeader, EmptyPanel,
} from '@/components/proof-panels';

export default function DashboardPage() {
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [health, setHealth] = React.useState<Health | null>(null);
  const [events, setEvents] = React.useState<TimelineEvent[]>([]);
  const [claims, setClaims] = React.useState<Claim[]>([]);
  const [contradictions, setContradictions] = React.useState<Contradiction[]>([]);
  const [obligations, setObligations] = React.useState<Obligation[]>([]);
  const [files, setFiles] = React.useState<FileSummary[]>([]);
  const [pipeline, setPipeline] = React.useState<PipelineEvent[]>([]);
  const [q, setQ] = React.useState('');
  const router = useRouter();

  React.useEffect(() => {
    void load();
  }, []);

  async function load() {
    try {
      const [s, h, t, cl, cn, ob, fs, pe] = await Promise.all([
        api.stats(),
        api.health(),
        api.timeline(),
        api.claims(),
        api.contradictions(),
        api.obligations(),
        api.listFiles(),
        api.pipelineEvents(),
      ]);
      setStats(s); setHealth(h); setEvents(t.slice(0, 25));
      setClaims(cl); setContradictions(cn); setObligations(ob);
      setFiles(fs); setPipeline(pe);
    } catch {
      /* ignore */
    }
  }

  const overdue = obligations.filter((o) => o.status === 'overdue').length;
  const supportedClaims = claims.filter((c) => c.status === 'supported').length;
  const contradictedClaims = claims.filter((c) => c.status === 'contradicted').length;

  const pipelineByFile = React.useMemo(() => {
    const m = new Map<string, PipelineEvent[]>();
    pipeline.forEach((e) => {
      const arr = m.get(e.file_id) || [];
      arr.push(e);
      m.set(e.file_id, arr);
    });
    return m;
  }, [pipeline]);

  return (
    <div className="space-y-8">
      <motion.section initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
          Search Your Life. Prove Everything.
        </h1>
        <p className="text-muted-fg text-sm mt-1">
          Every answer carries citations to the original source. Nothing leaves this machine.
        </p>
      </motion.section>

      <Card>
        <CardContent className="p-5">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
            }}
            className="flex gap-2"
          >
            <Input
              placeholder='Ask: "Did Sequoia change the price?" or "When is delivery due?"'
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="text-base h-11"
            />
            <Button size="lg" type="submit" className="gap-1">
              Ask <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
        </CardContent>
      </Card>

      <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Stat icon={<FileText className="h-4 w-4" />} label="Files" value={stats?.files ?? '—'} />
        <Stat icon={<Hash className="h-4 w-4" />} label="Chunks" value={stats?.chunks ?? '—'} />
        <Stat
          icon={<ListChecks className="h-4 w-4" />}
          label="Claims"
          value={claims.length || '—'}
          sub={claims.length ? `${supportedClaims} ok · ${contradictedClaims} flagged` : undefined}
        />
        <Stat
          icon={<GitFork className="h-4 w-4" />}
          label="Contradictions"
          value={contradictions.length}
          danger={contradictions.length > 0}
        />
        <Stat
          icon={<AlertTriangle className="h-4 w-4" />}
          label="Overdue"
          value={overdue}
          sub={obligations.length ? `of ${obligations.length} obligations` : undefined}
          danger={overdue > 0}
        />
        <Stat icon={<Clock className="h-4 w-4" />} label="Timeline" value={stats?.timeline_events ?? '—'} />
      </section>

      {(contradictions.length > 0 || obligations.length > 0) && (
        <section className="grid lg:grid-cols-2 gap-5">
          <div>
            <PanelHeader title="Contradictions" count={contradictions.length} />
            {contradictions.length === 0 ? (
              <EmptyPanel>No contradictions detected.</EmptyPanel>
            ) : (
              <div className="space-y-3">
                {contradictions.map((c) => <ContradictionCard key={c.id} c={c} />)}
              </div>
            )}
          </div>
          <div>
            <PanelHeader title="Obligations" count={obligations.length} />
            {obligations.length === 0 ? (
              <EmptyPanel>No tracked obligations.</EmptyPanel>
            ) : (
              <div className="space-y-2">
                {obligations.map((o) => <ObligationRow key={o.id} o={o} />)}
              </div>
            )}
          </div>
        </section>
      )}

      <section className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          <PanelHeader title="Recent activity" href="/timeline" />
          <Card>
            <CardContent className="p-5">
              {events.length === 0 ? (
                <EmptyPanel>No timeline events yet. Ingest some files first.</EmptyPanel>
              ) : (
                <TimelineView events={events} />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardContent className="p-5 space-y-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg">System</h2>
              <SystemRow label="Backend" ok={!!health?.ok} value={health?.version ?? '—'} />
              <SystemRow label="Database" ok={!!health?.db} value={health?.db ? 'sqlite' : 'down'} />
              <SystemRow label="Vector store" ok={!!health?.chroma} value={health?.chroma ? 'chroma' : 'down'} />
              <SystemRow label="LLM" ok={!!health?.ollama} value={health?.llm_model ?? '—'} />
              <SystemRow label="Embeddings" ok={true} value={health?.embed_model ?? '—'} />
              <div className="pt-2 border-t border-border">
                <Button asChild variant="secondary" size="sm" className="w-full">
                  <Link href="/import">Ingest files</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {claims.length > 0 && (
        <section>
          <PanelHeader title="Latest claims" count={claims.length} />
          <div className="space-y-2">
            {claims.slice(0, 6).map((cl) => <ClaimRow key={cl.id} claim={cl} />)}
          </div>
        </section>
      )}

      {files.length > 0 && (
        <section>
          <PanelHeader title="Ingestion pipeline" count={files.length} />
          <p className="text-xs text-muted-fg mb-3 flex items-center gap-1.5">
            <Activity className="h-3 w-3" />
            received → hashed → extracted → chunked → embedded → indexed → queryable
          </p>
          <div className="space-y-2">
            {files.map((f) => (
              <PipelineRow
                key={f.id}
                file={f}
                events={pipelineByFile.get(f.id) || []}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({
  icon, label, value, sub, danger,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  sub?: string;
  danger?: boolean;
}) {
  return (
    <Card className={danger ? 'border-danger/50 bg-danger/5' : undefined}>
      <CardContent className="p-3.5 flex items-start gap-3">
        <div className={`h-7 w-7 rounded-md grid place-items-center ${danger ? 'bg-danger/15 text-danger' : 'bg-accent/10 text-accent'}`}>
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wider text-muted-fg">{label}</div>
          <div className={`text-xl font-semibold tabular-nums ${danger ? 'text-danger' : ''}`}>{value}</div>
          {sub && <div className="text-[11px] text-muted-fg truncate">{sub}</div>}
        </div>
      </CardContent>
    </Card>
  );
}

function SystemRow({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-fg">{label}</span>
      <div className="flex items-center gap-2">
        <Badge variant={ok ? 'success' : 'danger'}>{ok ? 'ok' : 'down'}</Badge>
        <span className="text-fg/80 text-xs truncate max-w-[150px]">{value}</span>
      </div>
    </div>
  );
}
