'use client';

import * as React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Shield, FolderLock, Cpu, Wifi, WifiOff, Database } from 'lucide-react';
import { api, isDemoMode, subscribeDemoMode, type Health, type Stats } from '@/lib/api';
import { cn, relativeTime } from '@/lib/utils';

/**
 * A persistent strip just under the topbar that surfaces the privacy /
 * trust posture. Mirrors what's already true (local-first, citation-only,
 * no telemetry) and what's *currently* true (demo dataset vs real backend,
 * how stale the index is, which LLM is in use).
 *
 * Hidden on the /settings page since the same info is shown in detail there.
 */
export function TrustStrip() {
  const [demo, setDemo] = React.useState(isDemoMode());
  const [health, setHealth] = React.useState<Health | null>(null);
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [lastIngest, setLastIngest] = React.useState<string | null>(null);
  const path = usePathname();

  React.useEffect(() => subscribeDemoMode(setDemo), []);
  React.useEffect(() => {
    let cancelled = false;
    void Promise.all([api.health(), api.stats(), api.listFiles()]).then(
      ([h, s, fs]) => {
        if (cancelled) return;
        setHealth(h);
        setStats(s);
        const newest = fs
          .map((f) => f.ingested_at)
          .filter(Boolean)
          .sort()
          .at(-1) ?? null;
        setLastIngest(newest);
      },
    ).catch(() => { /* demo fallback or no backend */ });
    return () => { cancelled = true; };
  }, [demo]);

  if (path === '/settings') return null;

  const llmOk = !!health?.ollama;

  return (
    <div className="border-b border-border bg-surface/40 backdrop-blur-sm">
      <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-1.5 flex items-center gap-2 flex-wrap text-[11px] text-muted-fg">
        <Pill icon={<Shield className="h-3 w-3" />} tone="success" label="Local-first" />
        <Pill
          icon={<Database className="h-3 w-3" />}
          tone={demo ? 'accent' : 'success'}
          label={demo ? 'Demo dataset' : 'Live data'}
        />
        {stats && (
          <Pill
            icon={<FolderLock className="h-3 w-3" />}
            tone="default"
            label={`${stats.files} file${stats.files === 1 ? '' : 's'} · ${stats.chunks} chunks`}
          />
        )}
        {lastIngest && (
          <Pill
            icon={<Cpu className="h-3 w-3" />}
            tone="default"
            label={`Last ingest ${relativeTime(lastIngest)}`}
          />
        )}
        <Pill
          icon={llmOk ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
          tone={llmOk ? 'success' : 'warning'}
          label={llmOk ? `LLM: ${truncate(health?.llm_model ?? '', 28)}` : 'LLM offline'}
        />
        <Link
          href="/settings"
          className="ml-auto text-accent/80 hover:text-accent hover:underline shrink-0"
        >
          Privacy & data →
        </Link>
      </div>
    </div>
  );
}

function Pill({
  icon, label, tone,
}: {
  icon: React.ReactNode;
  label: string;
  tone: 'success' | 'warning' | 'accent' | 'default';
}) {
  const cls = {
    success: 'border-success/30 text-success/90 bg-success/5',
    warning: 'border-warning/40 text-warning bg-warning/5',
    accent:  'border-accent/40 text-accent bg-accent/5',
    default: 'border-border text-muted-fg bg-surface',
  }[tone];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5',
        cls,
      )}
    >
      {icon}
      <span className="whitespace-nowrap">{label}</span>
    </span>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}
