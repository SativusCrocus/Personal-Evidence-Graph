'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { FileText, Image as ImageIcon, Music, Globe, Clipboard, Film, File as FileIcon } from 'lucide-react';
import type { Citation, SourceType } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { formatTimecode } from '@/lib/utils';

const ICONS: Record<SourceType, React.ComponentType<{ className?: string }>> = {
  pdf: FileText,
  image: ImageIcon,
  audio: Music,
  text: FileText,
  browser: Globe,
  clipboard: Clipboard,
  video: Film,
  other: FileIcon,
};

export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-surface p-4 text-sm text-muted-fg">
        No citations.
      </div>
    );
  }
  return (
    <ol className="space-y-2.5">
      {citations.map((c, i) => (
        <motion.li
          key={c.chunk_id + i}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04 }}
        >
          <CitationCard c={c} index={i + 1} />
        </motion.li>
      ))}
    </ol>
  );
}

function CitationCard({ c, index }: { c: Citation; index: number }) {
  const Icon = ICONS[c.source_type] || FileIcon;
  const dt = c.source_dt ? new Date(c.source_dt).toLocaleString() : '—';
  const tc =
    c.ts_start_ms != null && c.ts_end_ms != null
      ? `${formatTimecode(c.ts_start_ms)} – ${formatTimecode(c.ts_end_ms)}`
      : null;
  return (
    <Link
      href={`/evidence/${encodeURIComponent(c.chunk_id)}`}
      className="block rounded-md border border-border bg-elevated hover:border-accent/40 hover:bg-accent/5 transition-colors group"
    >
      <div className="p-3 space-y-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="kbd">{index}</span>
          <Icon className="h-3.5 w-3.5 text-muted-fg" />
          <span className="font-medium text-fg truncate">{c.file_name}</span>
          <Badge variant="default" className="ml-auto shrink-0">
            score {c.score.toFixed(2)}
          </Badge>
        </div>
        <p className="text-sm leading-relaxed text-fg/90">
          <span className="bg-accent/10 text-accent rounded px-1">“{c.excerpt}”</span>
        </p>
        <div className="flex flex-wrap gap-1.5 text-[11px] text-muted-fg">
          <Badge>{c.source_type}</Badge>
          {c.page != null && <Badge>page {c.page}</Badge>}
          {tc && <Badge>{tc}</Badge>}
          <span className="ml-auto">{dt}</span>
        </div>
      </div>
    </Link>
  );
}
