'use client';

import * as React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, Database, FileText, Hash, Clock, Search } from 'lucide-react';
import { api, type Stats, type Health, type TimelineEvent } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { TimelineView } from '@/components/timeline-view';
import { useRouter } from 'next/navigation';

export default function DashboardPage() {
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [health, setHealth] = React.useState<Health | null>(null);
  const [events, setEvents] = React.useState<TimelineEvent[]>([]);
  const [q, setQ] = React.useState('');
  const router = useRouter();

  React.useEffect(() => {
    void load();
  }, []);

  async function load() {
    try {
      const [s, h, t] = await Promise.all([
        api.stats(),
        api.health(),
        api.timeline(),
      ]);
      setStats(s); setHealth(h); setEvents(t.slice(0, 25));
    } catch {
      /* ignore: empty backend */
    }
  }

  return (
    <div className="space-y-8">
      <motion.section initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">Search Your Life. Prove Everything.</h1>
        <p className="text-muted-fg text-sm mt-1">
          Every answer carries citations to the original source. Nothing leaves this machine.
        </p>
      </motion.section>

      <Card>
        <CardContent className="p-5">
          <form
            onSubmit={(e) => { e.preventDefault(); if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`); }}
            className="flex gap-2"
          >
            <Input
              placeholder='Ask: "Did the client approve the pricing?"'
              value={q} onChange={(e) => setQ(e.target.value)}
              className="text-base h-11"
            />
            <Button size="lg" type="submit" className="gap-1">
              Ask <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
        </CardContent>
      </Card>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat icon={<FileText className="h-4 w-4" />} label="Files indexed" value={stats?.files ?? '—'} />
        <Stat icon={<Hash className="h-4 w-4" />} label="Chunks" value={stats?.chunks ?? '—'} />
        <Stat icon={<Clock className="h-4 w-4" />} label="Timeline events" value={stats?.timeline_events ?? '—'} />
        <Stat icon={<Search className="h-4 w-4" />} label="Queries" value={stats?.queries ?? '—'}
          sub={stats ? `${stats.refused} refused` : undefined} />
      </section>

      <section className="grid lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg">Recent activity</h2>
              <Link href="/timeline" className="text-xs text-accent hover:underline">Open timeline →</Link>
            </div>
            <TimelineView events={events} />
          </CardContent>
        </Card>

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
      </section>
    </div>
  );
}

function Stat({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: React.ReactNode; sub?: string }) {
  return (
    <Card>
      <CardContent className="p-4 flex items-start gap-3">
        <div className="h-8 w-8 rounded-md bg-accent/10 grid place-items-center text-accent">{icon}</div>
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wider text-muted-fg">{label}</div>
          <div className="text-2xl font-semibold tabular-nums">{value}</div>
          {sub && <div className="text-[11px] text-muted-fg">{sub}</div>}
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
