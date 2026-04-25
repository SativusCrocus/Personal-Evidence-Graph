'use client';

import * as React from 'react';
import { Filter, GitFork, X } from 'lucide-react';
import {
  api, type TimelineEvent, type SourceType, type Contradiction,
} from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { TimelineView } from '@/components/timeline-view';
import { cn } from '@/lib/utils';

const SOURCE_TYPES: SourceType[] = [
  'pdf', 'image', 'audio', 'text', 'browser', 'clipboard', 'video', 'other',
];

export default function TimelinePage() {
  const [events, setEvents] = React.useState<TimelineEvent[]>([]);
  const [contradictions, setContradictions] = React.useState<Contradiction[]>([]);
  const [q, setQ] = React.useState('');
  const [from, setFrom] = React.useState('');
  const [to, setTo] = React.useState('');
  const [types, setTypes] = React.useState<Set<SourceType>>(new Set());
  const [kinds, setKinds] = React.useState<Set<string>>(new Set());
  const [contradictedOnly, setContradictedOnly] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  // Universe of kinds present in the loaded events — drives the kind filter chips.
  const knownKinds = React.useMemo(() => {
    const out = new Set<string>();
    events.forEach((e) => { if (e.kind) out.add(e.kind); });
    return Array.from(out).sort();
  }, [events]);

  // Chunks linked to active contradictions. Used to power the "contradicted only" filter.
  const contradictedChunks = React.useMemo(() => {
    const set = new Set<string>();
    contradictions.forEach((c) => c.related_chunk_ids.forEach((id) => set.add(id)));
    return set;
  }, [contradictions]);

  const filtered = React.useMemo(() => {
    return events.filter((e) => {
      if (types.size > 0 && !types.has(e.source_type)) return false;
      if (kinds.size > 0 && (!e.kind || !kinds.has(e.kind))) return false;
      if (contradictedOnly && (!e.chunk_id || !contradictedChunks.has(e.chunk_id))) return false;
      return true;
    });
  }, [events, types, kinds, contradictedOnly, contradictedChunks]);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [evs, cns] = await Promise.all([
        api.timeline({
          q: q || undefined,
          from: from ? new Date(from).toISOString() : undefined,
          to: to ? new Date(to).toISOString() : undefined,
        }),
        api.contradictions().catch(() => []),
      ]);
      setEvents(evs);
      setContradictions(cns);
    } catch {
      setEvents([]);
      setContradictions([]);
    } finally {
      setLoading(false);
    }
  }, [q, from, to]);

  React.useEffect(() => { void load(); }, [load]);

  const anyFilter =
    types.size > 0 || kinds.size > 0 || contradictedOnly;

  function clearFilters() {
    setTypes(new Set());
    setKinds(new Set());
    setContradictedOnly(false);
  }

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Timeline</h1>
          <p className="text-sm text-muted-fg">
            Reconstructed chronologically across every source.
          </p>
        </div>
      </header>

      <form
        onSubmit={(e) => { e.preventDefault(); void load(); }}
        className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto_auto] gap-2 items-end"
      >
        <Input
          placeholder="Filter by keyword in title…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        <Button type="submit" disabled={loading}>Apply</Button>
      </form>

      <section className="space-y-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-fg">
          <Filter className="h-3 w-3" />
          Filters
          {anyFilter && (
            <button
              type="button"
              onClick={clearFilters}
              className="ml-2 inline-flex items-center gap-1 text-accent hover:underline normal-case"
            >
              <X className="h-3 w-3" /> clear
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {SOURCE_TYPES.filter((t) => events.some((e) => e.source_type === t)).map((t) => (
            <FilterChip
              key={t}
              active={types.has(t)}
              onClick={() => setTypes((s) => toggle(s, t))}
            >
              {t}
            </FilterChip>
          ))}
        </div>

        {knownKinds.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {knownKinds.map((k) => (
              <FilterChip
                key={k}
                active={kinds.has(k)}
                onClick={() => setKinds((s) => toggle(s, k))}
              >
                {k}
              </FilterChip>
            ))}
          </div>
        )}

        {contradictions.length > 0 && (
          <div>
            <FilterChip
              active={contradictedOnly}
              tone="danger"
              onClick={() => setContradictedOnly((v) => !v)}
            >
              <GitFork className="h-3 w-3 inline mr-1" />
              contradictions only ({contradictions.length})
            </FilterChip>
          </div>
        )}

        <div className="text-xs text-muted-fg">
          Showing <span className="text-fg">{filtered.length}</span> of{' '}
          <span className="text-fg">{events.length}</span> events
          {anyFilter && ' (filtered)'}
        </div>
      </section>

      <TimelineView events={filtered} />
    </div>
  );
}

function FilterChip({
  active, onClick, tone, children,
}: {
  active: boolean;
  onClick: () => void;
  tone?: 'danger';
  children: React.ReactNode;
}) {
  const base = 'inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] uppercase tracking-wider transition-colors';
  const cls = active
    ? tone === 'danger'
      ? 'border-danger/60 bg-danger/15 text-danger'
      : 'border-accent/60 bg-accent/15 text-accent'
    : 'border-border bg-surface text-muted-fg hover:border-fg/30 hover:text-fg';
  return (
    <button type="button" onClick={onClick} className={cn(base, cls)}>
      {children}
    </button>
  );
}

function toggle<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}
