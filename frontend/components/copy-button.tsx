'use client';

import * as React from 'react';
import { Check, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export function CopyButton({
  text,
  label = 'Copy',
  size = 'sm',
  className,
}: {
  text: string;
  label?: string;
  size?: 'sm' | 'icon';
  className?: string;
}) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback for older browsers / restricted contexts.
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch { /* give up */ }
      ta.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  if (size === 'icon') {
    return (
      <Button
        variant="ghost"
        size="icon"
        onClick={copy}
        aria-label={copied ? 'Copied' : label}
        className={cn(className)}
      >
        {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={copy}
      className={cn('gap-1.5 text-xs', className)}
    >
      {copied ? (
        <><Check className="h-3 w-3 text-success" /> Copied</>
      ) : (
        <><Copy className="h-3 w-3" /> {label}</>
      )}
    </Button>
  );
}
