'use client';

import * as React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  AlertTriangle, CheckCircle2, HelpCircle, XCircle, Clock, Calendar,
  ArrowRightCircle, ChevronRight,
} from 'lucide-react';
import { format, formatDistanceToNowStrict, isPast, parseISO } from 'date-fns';
import type {
  Claim, ClaimStatus, Contradiction, ContradictionSeverity,
  Obligation, ObligationStatus,
} from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const STATUS_META: Record<ClaimStatus, { label: string; icon: React.ComponentType<{ className?: string }>; cls: string }> = {
  supported:    { label: 'Supported',    icon: CheckCircle2, cls: 'text-success' },
  contradicted: { label: 'Contradicted', icon: AlertTriangle, cls: 'text-danger' },
  uncertain:    { label: 'Uncertain',    icon: HelpCircle,    cls: 'text-warning' },
  refused:      { label: 'Refused',      icon: XCircle,       cls: 'text-muted-fg' },
};

export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  const m = STATUS_META[status];
  const Icon = m.icon;
  return (
    <span className={cn('inline-flex items-center gap-1 text-[11px] uppercase tracking-wider font-medium', m.cls)}>
      <Icon className="h-3 w-3" /> {m.label}
    </span>
  );
}

export function ClaimRow({ claim }: { claim: Claim }) {
  const m = STATUS_META[claim.status];
  const Icon = m.icon;
  return (
    <Link
      href={`/evidence/${encodeURIComponent(claim.source_chunk_id)}`}
      className="group flex items-start gap-3 rounded-md border border-border bg-elevated px-3 py-2.5 hover:border-accent/40 hover:bg-accent/5 transition-colors"
    >
      <Icon className={cn('h-4 w-4 mt-0.5 shrink-0', m.cls)} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium leading-snug">{claim.text}</div>
        <div className="text-[11px] text-muted-fg truncate mt-0.5">
          “{claim.source_excerpt}”
        </div>
      </div>
      <Badge className="shrink-0 mt-0.5">conf {Math.round(claim.confidence * 100)}%</Badge>
    </Link>
  );
}

const SEV_CLS: Record<ContradictionSeverity, string> = {
  low: 'border-warning/40 bg-warning/5',
  medium: 'border-warning/60 bg-warning/10',
  high: 'border-danger/60 bg-danger/10',
};

export function ContradictionCard({ c }: { c: Contradiction }) {
  return (
    <Card className={cn('border', SEV_CLS[c.severity])}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className={cn('h-4 w-4', c.severity === 'high' ? 'text-danger' : 'text-warning')} />
          <span className="text-xs uppercase tracking-wider font-semibold">
            {c.severity === 'high' ? 'High-severity contradiction' : 'Contradiction'}
          </span>
          <Badge className="ml-auto">{c.topic}</Badge>
        </div>
        <p className="text-sm leading-relaxed">{c.summary}</p>
        <div className="flex items-center justify-between text-[11px] text-muted-fg">
          <span>Detected {format(parseISO(c.detected_at), 'MMM d, HH:mm')}</span>
          <Link
            href={`/evidence/${encodeURIComponent(c.related_chunk_ids[0] ?? c.claim_ids[0])}`}
            className="inline-flex items-center gap-1 text-accent hover:underline"
          >
            Inspect <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

const OBLIG_CLS: Record<ObligationStatus, string> = {
  open: 'text-fg',
  overdue: 'text-danger',
  completed: 'text-success',
  cancelled: 'text-muted-fg',
};

export function ObligationRow({ o }: { o: Obligation }) {
  const due = parseISO(o.due_at);
  const overdue = o.status === 'overdue' || (o.status === 'open' && isPast(due));
  const rel = formatDistanceToNowStrict(due, { addSuffix: true });
  const ArrowIcon = o.direction === 'incoming' ? ArrowRightCircle : Calendar;
  return (
    <Link
      href={`/evidence/${encodeURIComponent(o.source_chunk_id)}`}
      className={cn(
        'group flex items-start gap-3 rounded-md border px-3 py-2.5 transition-colors',
        overdue ? 'border-danger/40 bg-danger/5 hover:bg-danger/10' : 'border-border bg-elevated hover:border-accent/40 hover:bg-accent/5',
      )}
    >
      <ArrowIcon className={cn('h-4 w-4 mt-0.5 shrink-0', OBLIG_CLS[overdue ? 'overdue' : o.status])} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium leading-snug">{o.text}</div>
        <div className="text-[11px] text-muted-fg truncate mt-0.5">
          {o.counterparty} · “{o.source_excerpt}”
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className={cn('text-[11px] uppercase tracking-wider font-semibold', OBLIG_CLS[overdue ? 'overdue' : o.status])}>
          {overdue ? 'Overdue' : o.status}
        </div>
        <div className="text-[11px] text-muted-fg">{rel}</div>
      </div>
    </Link>
  );
}

export function PanelHeader({ title, count, href }: { title: string; count?: number; href?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg flex items-center gap-2">
        {title}
        {typeof count === 'number' && <Badge>{count}</Badge>}
      </h2>
      {href && (
        <Link href={href} className="text-xs text-accent hover:underline">
          View all →
        </Link>
      )}
    </div>
  );
}

export function EmptyPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-border bg-surface p-5 text-center text-xs text-muted-fg">
      {children}
    </div>
  );
}

// ───────────────────────── pipeline ─────────────────────────

import type { FileSummary, PipelineEvent, PipelineStage, PipelineStatus } from '@/lib/api';

const STAGES: PipelineStage[] = [
  'received', 'hashed', 'extracted', 'chunked', 'embedded', 'indexed', 'queryable',
];

const STAGE_LABEL: Record<PipelineStage, string> = {
  received: 'recv',
  hashed: 'hash',
  extracted: 'extract',
  chunked: 'chunk',
  embedded: 'embed',
  indexed: 'index',
  queryable: 'query',
};

export function PipelineRow({
  file, events,
}: { file: FileSummary; events: PipelineEvent[] }) {
  const byStage = new Map<PipelineStage, PipelineEvent[]>();
  events.forEach((e) => {
    const arr = byStage.get(e.stage) || [];
    arr.push(e);
    byStage.set(e.stage, arr);
  });
  // Last successful stage reached:
  const reachedIdx = STAGES.reduce((acc, s, i) => {
    const evs = byStage.get(s) || [];
    return evs.some((e) => e.status === 'success') ? i : acc;
  }, -1);
  const hadFailure = events.some((e) => e.status === 'failed');
  const hadRetry = events.some((e) => e.status === 'retried');

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-md border border-border bg-elevated p-3 space-y-2"
    >
      <div className="flex items-center gap-2">
        <Badge variant="accent">{file.source_type}</Badge>
        <span className="text-sm font-medium truncate">{file.display_name}</span>
        <Badge
          className="ml-auto"
          variant={file.status === 'indexed' ? 'success' : file.status === 'failed' ? 'danger' : 'warning'}
        >
          {file.status}
        </Badge>
      </div>

      <ol className="flex items-center gap-1 overflow-x-auto pb-1">
        {STAGES.map((stage, i) => {
          const evs = byStage.get(stage) || [];
          const hasSuccess = evs.some((e) => e.status === 'success');
          const hasFailed = evs.some((e) => e.status === 'failed');
          const hasRetried = evs.some((e) => e.status === 'retried');
          const reached = i <= reachedIdx;
          let cls = 'border-border bg-surface text-muted-fg';
          let dot = 'bg-muted-fg/40';
          if (hasFailed && !hasSuccess) {
            cls = 'border-danger/60 bg-danger/10 text-danger';
            dot = 'bg-danger';
          } else if (hasRetried) {
            cls = 'border-warning/60 bg-warning/10 text-warning';
            dot = 'bg-warning';
          } else if (hasSuccess) {
            cls = 'border-success/40 bg-success/5 text-fg';
            dot = 'bg-success';
          } else if (!reached) {
            cls = 'border-border bg-surface text-muted-fg';
            dot = 'bg-muted-fg/30';
          }
          const lastFail = evs.findLast?.((e) => e.status === 'failed') ?? evs.find((e) => e.status === 'failed');
          return (
            <li key={stage} className="flex items-center gap-1 shrink-0">
              <div
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider',
                  cls,
                )}
                title={lastFail?.message ?? stage}
              >
                <span className={cn('h-1.5 w-1.5 rounded-full', dot)} />
                {STAGE_LABEL[stage]}
              </div>
              {i < STAGES.length - 1 && <span className="text-muted-fg/40 text-[10px]">→</span>}
            </li>
          );
        })}
      </ol>

      {(hadFailure || hadRetry) && (
        <div className="text-[11px] text-muted-fg">
          {events
            .filter((e) => e.status === 'failed' || e.status === 'retried')
            .map((e) => (
              <div key={e.id} className={cn(e.status === 'failed' ? 'text-danger' : 'text-warning')}>
                {e.status === 'failed' ? '✗' : '↻'} {e.stage}: {e.message ?? e.status}
              </div>
            ))}
        </div>
      )}
    </motion.div>
  );
}

const _statusOk: PipelineStatus = 'success'; void _statusOk;
