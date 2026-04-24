'use client';

import * as React from 'react';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useCommandPalette } from '@/components/command-palette';
import { isDemoMode, subscribeDemoMode } from '@/lib/api';

export function Topbar() {
  const { open } = useCommandPalette();
  const [demo, setDemo] = React.useState(isDemoMode());
  React.useEffect(() => subscribeDemoMode(setDemo), []);

  return (
    <header className="h-14 border-b border-border bg-surface/80 backdrop-blur sticky top-0 z-30">
      <div className="h-full px-4 md:px-6 flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={open}
          className="gap-2 text-muted-fg hover:text-fg w-full max-w-md justify-between"
        >
          <span className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5" />
            Ask anything…
          </span>
          <span className="kbd">⌘ K</span>
        </Button>
        <div className="ml-auto flex items-center gap-2 text-[11px] text-muted-fg">
          <span className="hidden sm:inline">{demo ? 'Demo dataset' : '100% local'}</span>
          <span className={`h-1.5 w-1.5 rounded-full ${demo ? 'bg-accent' : 'bg-success'}`} />
        </div>
      </div>
    </header>
  );
}
