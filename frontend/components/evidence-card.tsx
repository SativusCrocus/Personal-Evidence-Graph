'use client';

import { Badge } from '@/components/ui/badge';
import type { ChunkOut, FileSummary } from '@/lib/api';
import { formatTimecode } from '@/lib/utils';

export function EvidenceCard({ chunk, file }: { chunk: ChunkOut; file: FileSummary }) {
  const tc =
    chunk.ts_start_ms != null && chunk.ts_end_ms != null
      ? `${formatTimecode(chunk.ts_start_ms)} – ${formatTimecode(chunk.ts_end_ms)}`
      : null;
  return (
    <article className="rounded-md border border-border bg-elevated p-4 space-y-2">
      <div className="flex items-center gap-2 text-xs">
        <span className="font-medium text-fg truncate">{file.display_name}</span>
        <Badge variant="accent">chunk #{chunk.ord}</Badge>
        {chunk.page != null && <Badge>page {chunk.page}</Badge>}
        {tc && <Badge>{tc}</Badge>}
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-fg/90">{chunk.text}</p>
    </article>
  );
}
