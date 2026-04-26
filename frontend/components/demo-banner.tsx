'use client';

import * as React from 'react';
import Link from 'next/link';
import { Sparkles, X, ExternalLink, RefreshCw, AlertTriangle } from 'lucide-react';
import { subscribeDemoMode, retryBackendProbe } from '@/lib/api';

const DISMISS_KEY = 'evg.demo-banner.dismissed.v1';

export function DemoBanner() {
  const [demo, setDemo] = React.useState(false);
  const [dismissed, setDismissed] = React.useState(false);
  const [probing, setProbing] = React.useState(false);
  const [lastError, setLastError] = React.useState<string | null>(null);

  React.useEffect(() => subscribeDemoMode(setDemo), []);
  React.useEffect(() => {
    setDismissed(typeof window !== 'undefined' && window.localStorage.getItem(DISMISS_KEY) === '1');
  }, []);

  async function tryReconnect() {
    setProbing(true);
    setLastError(null);
    const r = await retryBackendProbe();
    setProbing(false);
    if (r.ok) {
      // Backend is reachable — reload so every page re-fetches against real data.
      window.location.reload();
    } else {
      setLastError(r.error ?? 'unreachable');
    }
  }

  if (!demo || dismissed) return null;

  return (
    <div className="border-b border-accent/30 bg-gradient-to-r from-accent/10 via-accent/5 to-transparent">
      <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-2.5 flex items-center gap-3 text-xs flex-wrap">
        <Sparkles className="h-3.5 w-3.5 text-accent shrink-0" />
        <span className="text-fg/90 min-w-0">
          <strong className="text-accent">Demo mode</strong>
          <span className="text-muted-fg"> — your local backend isn't reachable, so this view is showing a seeded dataset.</span>
        </span>

        <button
          onClick={tryReconnect}
          disabled={probing}
          className="inline-flex items-center gap-1 rounded-md border border-accent/40 bg-accent/10 px-2 py-0.5 text-accent hover:bg-accent/20 disabled:opacity-60 shrink-0"
          title="Re-probe http://localhost:8000/health"
        >
          <RefreshCw className={`h-3 w-3 ${probing ? 'animate-spin' : ''}`} />
          {probing ? 'Probing…' : 'Try local backend'}
        </button>

        {lastError && (
          <span className="inline-flex items-center gap-1 text-warning shrink-0">
            <AlertTriangle className="h-3 w-3" />
            {lastError}
          </span>
        )}

        <Link
          href="https://github.com/SativusCrocus/Personal-Evidence-Graph#install"
          className="ml-auto hidden md:inline-flex items-center gap-1 text-accent hover:underline shrink-0"
          target="_blank"
          rel="noreferrer"
        >
          Install docs <ExternalLink className="h-3 w-3" />
        </Link>
        <button
          onClick={() => {
            window.localStorage.setItem(DISMISS_KEY, '1');
            setDismissed(true);
          }}
          aria-label="Dismiss demo banner"
          className="text-muted-fg hover:text-fg shrink-0"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
