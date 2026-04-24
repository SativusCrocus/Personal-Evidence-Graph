'use client';

import * as React from 'react';
import { api, type TimelineEvent } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { TimelineView } from '@/components/timeline-view';

export default function TimelinePage() {
  const [events, setEvents] = React.useState<TimelineEvent[]>([]);
  const [q, setQ] = React.useState('');
  const [from, setFrom] = React.useState('');
  const [to, setTo] = React.useState('');
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setEvents(await api.timeline({
        q: q || undefined,
        from: from ? new Date(from).toISOString() : undefined,
        to: to ? new Date(to).toISOString() : undefined,
      }));
    } catch {
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [q, from, to]);

  React.useEffect(() => { void load(); }, [load]);

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Timeline</h1>
          <p className="text-sm text-muted-fg">Reconstructed chronologically across every source.</p>
        </div>
      </header>
      <form
        onSubmit={(e) => { e.preventDefault(); void load(); }}
        className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto_auto] gap-2 items-end"
      >
        <Input placeholder="Filter by keyword in title…" value={q} onChange={(e) => setQ(e.target.value)} />
        <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        <Button type="submit" disabled={loading}>Apply</Button>
      </form>
      <TimelineView events={events} />
    </div>
  );
}
