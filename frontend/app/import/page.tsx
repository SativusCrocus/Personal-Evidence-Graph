'use client';

import * as React from 'react';
import { motion } from 'framer-motion';
import { Folder } from 'lucide-react';
import { api, type FileSummary } from '@/lib/api';
import { UploadDropzone } from '@/components/upload-dropzone';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatBytes, relativeTime } from '@/lib/utils';

export default function ImportPage() {
  const [files, setFiles] = React.useState<FileSummary[]>([]);
  const [folder, setFolder] = React.useState('');
  const [folderBusy, setFolderBusy] = React.useState(false);
  const [folderResult, setFolderResult] = React.useState<string | null>(null);

  React.useEffect(() => { void refresh(); }, []);
  async function refresh() {
    try { setFiles(await api.listFiles()); } catch { setFiles([]); }
  }
  React.useEffect(() => {
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, []);

  async function ingestFolder() {
    if (!folder.trim()) return;
    setFolderBusy(true); setFolderResult(null);
    try {
      const res = await api.ingestFolder(folder.trim());
      setFolderResult(`Queued ${res.length} file(s).`);
      await refresh();
    } catch (e) {
      setFolderResult(e instanceof Error ? e.message : 'failed');
    } finally {
      setFolderBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Import evidence</h1>
        <p className="text-sm text-muted-fg">
          Drop files, or point at a folder under one of your watched roots.
        </p>
      </header>

      <section>
        <UploadDropzone />
      </section>

      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg flex items-center gap-2">
            <Folder className="h-4 w-4" /> Ingest a folder
          </h2>
          <p className="text-xs text-muted-fg">
            Path must be inside <code>EVG_WATCHED_ROOTS</code> or <code>EVG_DATA_DIR</code>.
          </p>
          <div className="flex gap-2">
            <Input
              placeholder="/Users/you/Documents/contracts"
              value={folder} onChange={(e) => setFolder(e.target.value)}
            />
            <Button onClick={ingestFolder} disabled={folderBusy || !folder.trim()}>
              {folderBusy ? 'Ingesting…' : 'Ingest'}
            </Button>
          </div>
          {folderResult && <div className="text-xs text-muted-fg">{folderResult}</div>}
        </CardContent>
      </Card>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg mb-3">
          Recent ingestions ({files.length})
        </h2>
        <div className="space-y-2">
          {files.length === 0 && (
            <div className="rounded-md border border-dashed border-border p-8 text-sm text-muted-fg text-center">
              Nothing ingested yet.
            </div>
          )}
          {files.map((f, i) => (
            <motion.div key={f.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.01 }}>
              <Card>
                <CardContent className="p-3 flex items-center gap-3">
                  <Badge variant="accent">{f.source_type}</Badge>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{f.display_name}</div>
                    <div className="text-[11px] text-muted-fg flex gap-2">
                      <span>{formatBytes(f.bytes)}</span>
                      <span>{f.chunk_count} chunks</span>
                      <span>{relativeTime(f.ingested_at)}</span>
                    </div>
                  </div>
                  <Badge variant={f.status === 'indexed' ? 'success' : f.status === 'failed' ? 'danger' : 'warning'}>
                    {f.status}
                  </Badge>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
