'use client';

import * as React from 'react';
import Link from 'next/link';
import { Sparkles, X, ExternalLink } from 'lucide-react';
import { subscribeDemoMode } from '@/lib/api';

const DISMISS_KEY = 'evg.demo-banner.dismissed.v1';

export function DemoBanner() {
  const [demo, setDemo] = React.useState(false);
  const [dismissed, setDismissed] = React.useState(false);

  React.useEffect(() => subscribeDemoMode(setDemo), []);
  React.useEffect(() => {
    setDismissed(typeof window !== 'undefined' && window.localStorage.getItem(DISMISS_KEY) === '1');
  }, []);

  if (!demo || dismissed) return null;

  return (
    <div className="border-b border-accent/30 bg-gradient-to-r from-accent/10 via-accent/5 to-transparent">
      <div className="max-w-[1400px] mx-auto px-4 md:px-8 py-2.5 flex items-center gap-3 text-xs">
        <Sparkles className="h-3.5 w-3.5 text-accent shrink-0" />
        <span className="text-fg/90">
          <strong className="text-accent">Demo mode</strong>
          <span className="text-muted-fg"> — your local backend isn't reachable, so this view is showing a seeded dataset (one vendor, one contradiction, one overdue obligation).</span>
        </span>
        <Link
          href="https://github.com/SativusCrocus/Personal-Evidence-Graph#install"
          className="ml-auto hidden sm:inline-flex items-center gap-1 text-accent hover:underline shrink-0"
          target="_blank"
          rel="noreferrer"
        >
          Run it on your machine <ExternalLink className="h-3 w-3" />
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
