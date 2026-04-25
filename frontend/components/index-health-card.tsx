'use client';

import * as React from 'react';
import {
  Activity, AlertTriangle, Clock, Cpu, Database, FileWarning,
  GitFork, ListChecks, MessageSquare, Hash,
} from 'lucide-react';
import { api, type IndexHealth } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn, formatBytes, relativeTime } from '@/lib/utils';

/**
 * Operational telemetry card for the dashboard. Shows the things an oncall
 * person would actually want at a glance: how stale the index is, how many
 * files failed extraction, what's queued behind OCR, and when the LLM was
 * last reachable.
 */
export function IndexHealthCard() {
  const [h, setH] = React.useState<IndexHealth | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    void api.indexHealth().then((x) => { if (!cancelled) setH(x); }).catch(() => { /* ok */ });
    return () => { cancelled = true; };
  }, []);

  if (!h) return null;

  const hot = h.failed_files > 0 || h.ocr_backlog > 0 || h.embedding_queue_depth > 0;
  const llmStale = h.last_llm_call_at
    ? Date.now() - Date.parse(h.last_llm_call_at) > 24 * 3600 * 1000
    : true;

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Index health
          </h2>
          <Badge variant={hot ? 'warning' : 'success'}>
            {hot ? 'attention' : 'green'}
          </Badge>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <Metric icon={<Hash className="h-3.5 w-3.5" />} label="Chunks" value={h.total_chunks} />
          <Metric icon={<ListChecks className="h-3.5 w-3.5" />} label="Claims" value={h.total_claims} />
          <Metric icon={<MessageSquare className="h-3.5 w-3.5" />} label="Obligations" value={h.total_obligations} />
          <Metric
            icon={<GitFork className="h-3.5 w-3.5" />}
            label="Contradictions"
            value={h.total_contradictions}
            danger={h.total_contradictions > 0}
          />
          <Metric
            icon={<FileWarning className="h-3.5 w-3.5" />}
            label="Failed files"
            value={h.failed_files}
            danger={h.failed_files > 0}
          />
          <Metric
            icon={<Database className="h-3.5 w-3.5" />}
            label="DB size"
            value={formatBytes(h.db_bytes)}
          />
        </div>

        <div className="space-y-1.5 text-xs border-t border-border pt-3">
          <Row
            icon={<Clock className="h-3.5 w-3.5" />}
            label="Last ingest"
            value={h.last_ingest_at ? relativeTime(h.last_ingest_at) : 'never'}
          />
          <Row
            icon={<MessageSquare className="h-3.5 w-3.5" />}
            label="Last query"
            value={h.last_query_at ? relativeTime(h.last_query_at) : 'never'}
          />
          <Row
            icon={<Cpu className="h-3.5 w-3.5" />}
            label="Last LLM call"
            value={h.last_llm_call_at ? relativeTime(h.last_llm_call_at) : 'never'}
            tone={llmStale ? 'warning' : undefined}
          />
          {h.index_age_seconds != null && (
            <Row
              icon={<Activity className="h-3.5 w-3.5" />}
              label="Earliest source"
              value={ageString(h.index_age_seconds)}
            />
          )}
          <Row
            icon={<Cpu className="h-3.5 w-3.5" />}
            label="Vector dim"
            value={String(h.vector_dim)}
          />
          {(h.ocr_backlog > 0 || h.embedding_queue_depth > 0) && (
            <Row
              icon={<AlertTriangle className="h-3.5 w-3.5" />}
              label="Queues"
              tone="warning"
              value={`OCR ${h.ocr_backlog} · embed ${h.embedding_queue_depth}`}
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({
  icon, label, value, danger,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <div className={cn(
      'rounded-md border bg-elevated px-3 py-2',
      danger ? 'border-danger/40 bg-danger/5' : 'border-border',
    )}>
      <div className="text-[10px] uppercase tracking-wider text-muted-fg flex items-center gap-1">
        <span className={danger ? 'text-danger' : 'text-muted-fg'}>{icon}</span>
        {label}
      </div>
      <div className={cn('text-base font-semibold tabular-nums mt-0.5',
        danger && 'text-danger')}>{value}</div>
    </div>
  );
}

function Row({
  icon, label, value, tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: 'warning';
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-muted-fg">
        {icon}
        {label}
      </span>
      <span className={cn(
        'tabular-nums',
        tone === 'warning' ? 'text-warning' : 'text-fg/80',
      )}>{value}</span>
    </div>
  );
}

function ageString(seconds: number): string {
  const days = Math.round(seconds / 86_400);
  if (days < 1) return `${Math.round(seconds / 3600)}h ago`;
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  return `${months}mo ago`;
}
