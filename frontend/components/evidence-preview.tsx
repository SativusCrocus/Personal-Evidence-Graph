'use client';

import * as React from 'react';
import { api, type FileSummary, type SourceType } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { formatTimecode } from '@/lib/utils';

export function EvidencePreview({ file, ts_start_ms }: {
  file: FileSummary;
  ts_start_ms?: number | null;
}) {
  const url = api.fileRawUrl(file.id);
  return (
    <div className="rounded-md border border-border bg-elevated overflow-hidden flex flex-col">
      <div className="p-3 flex items-center gap-2 border-b border-border bg-surface">
        <Badge variant="accent">{file.source_type}</Badge>
        <div className="text-xs text-muted-fg truncate flex-1">{file.path}</div>
        <Button asChild variant="ghost" size="sm" className="gap-1.5 text-xs">
          <a href={url} target="_blank" rel="noreferrer">
            Open <ExternalLink className="h-3 w-3" />
          </a>
        </Button>
      </div>
      <div className="flex-1 min-h-[60vh] bg-bg">
        {renderPreview(file.source_type, url, ts_start_ms ?? null)}
      </div>
    </div>
  );
}

function renderPreview(type: SourceType, url: string, ts_start_ms: number | null) {
  if (type === 'image') {
    return <img src={url} alt="" className="w-full h-full object-contain" />;
  }
  if (type === 'pdf') {
    return (
      <iframe
        src={url}
        className="w-full h-full min-h-[60vh] border-0"
        sandbox="allow-same-origin"
        title="pdf preview"
      />
    );
  }
  if (type === 'audio') {
    return (
      <div className="p-6">
        <div className="text-xs text-muted-fg mb-2">
          {ts_start_ms != null && <>Highlighted segment starts at {formatTimecode(ts_start_ms)}</>}
        </div>
        <audio
          src={ts_start_ms != null ? `${url}#t=${(ts_start_ms / 1000).toFixed(1)}` : url}
          controls
          className="w-full"
        />
      </div>
    );
  }
  if (type === 'video') {
    return (
      <video
        src={ts_start_ms != null ? `${url}#t=${(ts_start_ms / 1000).toFixed(1)}` : url}
        controls
        className="w-full max-h-[80vh]"
      />
    );
  }
  if (type === 'browser' || type === 'text' || type === 'clipboard') {
    return (
      <iframe
        src={url}
        className="w-full h-full min-h-[60vh] border-0"
        sandbox="allow-same-origin"
        title="text preview"
      />
    );
  }
  return (
    <div className="p-6 text-sm text-muted-fg">
      No inline preview for {type}. <a href={url} target="_blank" rel="noreferrer" className="text-accent">Download</a>.
    </div>
  );
}
