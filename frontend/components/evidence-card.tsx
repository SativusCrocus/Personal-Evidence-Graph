'use client';

import { Badge } from '@/components/ui/badge';
import type { ChunkOut, FileSummary } from '@/lib/api';
import { formatTimecode } from '@/lib/utils';
import { CopyButton } from '@/components/copy-button';
import { HighlightedText } from '@/components/highlighted-text';

export function EvidenceCard({
  chunk,
  file,
  highlights = [],
  emphasised = false,
}: {
  chunk: ChunkOut;
  file: FileSummary;
  /** Excerpts to highlight inside the chunk text (verbatim, whitespace-tolerant). */
  highlights?: string[];
  /** Slightly stronger ring + accent border to distinguish "this is the chunk you came from". */
  emphasised?: boolean;
}) {
  const tc =
    chunk.ts_start_ms != null && chunk.ts_end_ms != null
      ? `${formatTimecode(chunk.ts_start_ms)} – ${formatTimecode(chunk.ts_end_ms)}`
      : null;
  return (
    <article
      className={
        'rounded-md border p-4 space-y-2 ' +
        (emphasised ? 'border-accent/50 bg-accent/[0.04] ring-1 ring-accent/20' : 'border-border bg-elevated')
      }
    >
      <div className="flex items-center gap-2 text-xs">
        <span className="font-medium text-fg truncate">{file.display_name}</span>
        <Badge variant="accent">chunk #{chunk.ord}</Badge>
        {chunk.page != null && <Badge>page {chunk.page}</Badge>}
        {tc && <Badge>{tc}</Badge>}
        <CopyButton size="icon" className="ml-auto -my-1" text={chunk.text} label="Copy chunk text" />
      </div>
      <HighlightedText text={chunk.text} excerpts={highlights} />
    </article>
  );
}
