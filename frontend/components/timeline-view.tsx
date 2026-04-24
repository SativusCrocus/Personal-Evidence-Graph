'use client';

import * as React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { format } from 'date-fns';
import { FileText, Image as ImageIcon, Music, Globe, Clipboard, Film, File as FileIcon } from 'lucide-react';
import type { TimelineEvent, SourceType } from '@/lib/api';
import { Badge } from '@/components/ui/badge';

const ICONS: Record<SourceType, React.ComponentType<{ className?: string }>> = {
  pdf: FileText, image: ImageIcon, audio: Music, text: FileText,
  browser: Globe, clipboard: Clipboard, video: Film, other: FileIcon,
};

export function TimelineView({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-fg">
        No timeline events yet. Ingest some files first.
      </div>
    );
  }
  const grouped = groupByDay(events);
  return (
    <div className="space-y-8 relative">
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" aria-hidden />
      {grouped.map((group, gi) => (
        <div key={group.day} className="space-y-3">
          <div className="flex items-center gap-3 sticky top-14 z-10 bg-bg/80 backdrop-blur py-1">
            <div className="h-3.5 w-3.5 rounded-full bg-accent shadow-[0_0_0_4px_hsl(var(--bg))]" />
            <div className="text-xs uppercase tracking-wider text-muted-fg font-medium">
              {format(new Date(group.day), 'EEE, MMM d, yyyy')}
            </div>
            <Badge>{group.events.length}</Badge>
          </div>
          <ol className="space-y-2 pl-7">
            {group.events.map((e, i) => {
              const Icon = ICONS[e.source_type] || FileIcon;
              const target = e.chunk_id ? `/evidence/${e.chunk_id}` : `/search?q=${encodeURIComponent(e.title)}`;
              return (
                <motion.li
                  key={e.id}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: gi * 0.02 + i * 0.015 }}
                >
                  <Link
                    href={target}
                    className="group flex items-start gap-3 rounded-md border border-border bg-elevated px-3 py-2.5 hover:border-accent/40 hover:bg-accent/5 transition-colors"
                  >
                    <Icon className="h-4 w-4 text-muted-fg mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium truncate">{e.title}</div>
                      <div className="text-[11px] text-muted-fg truncate">
                        {e.file_name}
                        {e.kind && <> · {e.kind}</>}
                      </div>
                    </div>
                    <div className="text-[11px] text-muted-fg shrink-0">
                      {format(new Date(e.occurred_at), 'HH:mm')}
                    </div>
                  </Link>
                </motion.li>
              );
            })}
          </ol>
        </div>
      ))}
    </div>
  );
}

function groupByDay(events: TimelineEvent[]) {
  const map = new Map<string, TimelineEvent[]>();
  for (const e of events) {
    const day = e.occurred_at.slice(0, 10);
    const arr = map.get(day) || [];
    arr.push(e);
    map.set(day, arr);
  }
  return Array.from(map.entries())
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([day, evs]) => ({ day, events: evs }));
}
