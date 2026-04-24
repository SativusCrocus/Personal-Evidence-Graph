'use client';

import * as React from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { CloudUpload, CheckCircle2, X, Loader2, AlertTriangle } from 'lucide-react';
import { api, type IngestResponse } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, formatBytes } from '@/lib/utils';

type Item = {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'done' | 'error';
  result?: IngestResponse;
  error?: string;
};

export function UploadDropzone() {
  const [items, setItems] = React.useState<Item[]>([]);

  const onDrop = React.useCallback((accepted: File[]) => {
    const next = accepted.map((f) => ({
      id: `${f.name}_${f.size}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      file: f,
      status: 'pending' as const,
    }));
    setItems((prev) => [...next, ...prev]);
    next.forEach((it) => void uploadOne(it));
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxSize: 200 * 1024 * 1024,
  });

  async function uploadOne(it: Item) {
    setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, status: 'uploading' } : x)));
    try {
      const result = await api.ingestFile(it.file);
      setItems((prev) =>
        prev.map((x) => (x.id === it.id ? { ...x, status: 'done', result } : x))
      );
    } catch (e) {
      setItems((prev) =>
        prev.map((x) =>
          x.id === it.id ? { ...x, status: 'error', error: e instanceof Error ? e.message : 'failed' } : x
        )
      );
    }
  }

  function dismiss(id: string) {
    setItems((prev) => prev.filter((x) => x.id !== id));
  }

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          'rounded-lg border-2 border-dashed border-border bg-surface text-center px-6 py-14 cursor-pointer',
          'transition-colors hover:border-accent/60 hover:bg-accent/5',
          isDragActive && 'border-accent bg-accent/10'
        )}
      >
        <input {...getInputProps()} />
        <CloudUpload className="h-10 w-10 mx-auto text-muted-fg mb-3" />
        <p className="text-sm font-medium">
          {isDragActive ? 'Drop to ingest' : 'Drag & drop files, or click to choose'}
        </p>
        <p className="text-xs text-muted-fg mt-1">
          PDFs, images, audio, text · 100MB / file · processed locally
        </p>
      </div>

      <AnimatePresence>
        {items.map((it) => (
          <motion.div
            key={it.id}
            layout
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
          >
            <Card className="hover:border-border">
              <CardContent className="p-3 flex items-center gap-3">
                <StatusIcon status={it.status} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{it.file.name}</div>
                  <div className="text-[11px] text-muted-fg flex gap-2">
                    <span>{formatBytes(it.file.size)}</span>
                    {it.result?.duplicate && <Badge variant="warning">duplicate</Badge>}
                    {it.error && <span className="text-danger truncate">{it.error}</span>}
                  </div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => dismiss(it.id)}>
                  <X className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function StatusIcon({ status }: { status: Item['status'] }) {
  if (status === 'uploading') return <Loader2 className="h-4 w-4 animate-spin text-accent" />;
  if (status === 'done') return <CheckCircle2 className="h-4 w-4 text-success" />;
  if (status === 'error') return <AlertTriangle className="h-4 w-4 text-danger" />;
  return <CloudUpload className="h-4 w-4 text-muted-fg" />;
}
