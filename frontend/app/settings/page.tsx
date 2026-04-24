'use client';

import * as React from 'react';
import { api, type Health, type Stats } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export default function SettingsPage() {
  const [health, setHealth] = React.useState<Health | null>(null);
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [reindexing, setReindexing] = React.useState(false);
  const [msg, setMsg] = React.useState<string | null>(null);

  React.useEffect(() => {
    void load();
  }, []);
  async function load() {
    try {
      setHealth(await api.health());
      setStats(await api.stats());
    } catch {
      /* ignore */
    }
  }

  async function reindex() {
    setReindexing(true); setMsg(null);
    try {
      await api.reindex();
      setMsg('Reindex queued. Check the dashboard for progress.');
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'failed');
    } finally {
      setReindexing(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-fg">
          The backend reads <code>.env</code> at startup. Edit <code>backend/.env</code> and restart to change models or paths.
        </p>
      </header>

      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg">Models</h2>
          <Row label="LLM (Ollama)" value={health?.llm_model ?? '—'} ok={!!health?.ollama} />
          <Row label="Embeddings" value={health?.embed_model ?? '—'} ok />
          <p className="text-xs text-muted-fg pt-1">
            Switch models by setting <code>EVG_LLM_MODEL</code>, <code>EVG_EMBED_MODEL</code>.
            Pull new models with <code>scripts/pull_models.sh</code>.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg">Storage</h2>
          <Row label="Database" value={health?.db ? 'sqlite, healthy' : 'unavailable'} ok={!!health?.db} />
          <Row label="Vector store" value={health?.chroma ? 'chroma, healthy' : 'unavailable'} ok={!!health?.chroma} />
          <Row label="Files indexed" value={String(stats?.files ?? 0)} ok />
          <Row label="Chunks" value={String(stats?.chunks ?? 0)} ok />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg">Maintenance</h2>
          <p className="text-sm text-muted-fg">
            Rebuild the vector index from SQLite. Safe; runs in the background.
          </p>
          <div className="flex items-center gap-2">
            <Button onClick={reindex} disabled={reindexing}>
              {reindexing ? 'Queueing…' : 'Rebuild index'}
            </Button>
            {msg && <span className="text-xs text-muted-fg">{msg}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5 space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-fg">Privacy</h2>
          <p className="text-sm">
            Personal Evidence Graph runs <strong>entirely on this machine</strong>. No telemetry. No cloud calls.
            Files, embeddings, and the LLM all stay local.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-fg">{label}</span>
      <div className="flex items-center gap-2">
        <Badge variant={ok ? 'success' : 'danger'}>{ok ? 'ok' : 'down'}</Badge>
        <span className="text-fg/80">{value}</span>
      </div>
    </div>
  );
}
