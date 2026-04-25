'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Command } from 'cmdk';
import {
  LayoutDashboard, Search, Clock, Upload, Settings as SettingsIcon, Sparkles,
  Hammer, AlertTriangle, GitFork, MessageSquare, Star, FileWarning, FolderInput,
  RefreshCw, CheckCircle2,
} from 'lucide-react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { api } from '@/lib/api';

interface PaletteCtx {
  open: () => void;
  close: () => void;
  isOpen: boolean;
}
const Ctx = React.createContext<PaletteCtx | null>(null);

export function useCommandPalette(): PaletteCtx {
  const c = React.useContext(Ctx);
  if (!c) throw new Error('useCommandPalette must be used within CommandPaletteProvider');
  return c;
}

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<{ msg: string; tone: 'ok' | 'err' } | null>(null);
  const [query, setQuery] = React.useState('');
  const router = useRouter();

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  React.useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2200);
    return () => window.clearTimeout(t);
  }, [toast]);

  const ctx: PaletteCtx = {
    open: () => setOpen(true),
    close: () => setOpen(false),
    isOpen,
  };

  function go(href: string) {
    setOpen(false);
    setQuery('');
    router.push(href);
  }
  function ask(q: string) {
    if (!q.trim()) return;
    setOpen(false);
    setQuery('');
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  async function withBusy(label: string, fn: () => Promise<void>) {
    setBusy(label);
    try {
      await fn();
      setToast({ msg: `${label} ✓`, tone: 'ok' });
    } catch (e) {
      setToast({ msg: e instanceof Error ? e.message : `${label} failed`, tone: 'err' });
    } finally {
      setBusy(null);
      setOpen(false);
      setQuery('');
    }
  }

  // ──────── action handlers ────────

  async function actionReindex() {
    await withBusy('Reindex queued', async () => {
      await api.reindex();
    });
  }

  async function actionJumpToMostCited() {
    await withBusy('Jumping to most-cited source', async () => {
      const files = await api.listFiles();
      if (!files.length) throw new Error('no files yet');
      const top = files.slice().sort((a, b) => b.chunk_count - a.chunk_count)[0];
      // Pick its first chunk via /evidence — we get a chunk_id from claims
      // (most reliable) or from the first chunk of the file.
      const claims = await api.claims({ file_id: top.id });
      if (claims[0]?.source_chunk_id) {
        router.push(`/evidence/${encodeURIComponent(claims[0].source_chunk_id)}`);
      } else {
        router.push(`/import`);
      }
    });
  }

  async function actionOpenLatestFailure() {
    await withBusy('Opening latest failure', async () => {
      const events = await api.pipelineEvents();
      const failed = events
        .filter((e) => e.status === 'failed')
        .sort((a, b) => (a.at < b.at ? 1 : -1));
      if (!failed.length) throw new Error('no failures recorded');
      // Jump to the dashboard pipeline view — it shows the failed badge inline.
      router.push(`/dashboard#pipeline`);
    });
  }

  async function actionShowContradictions() {
    setOpen(false);
    setQuery('');
    router.push('/dashboard#contradictions');
  }

  async function actionShowOverdue() {
    setOpen(false);
    setQuery('');
    router.push('/dashboard#obligations');
  }

  return (
    <Ctx.Provider value={ctx}>
      {children}
      {toast && (
        <div
          role="status"
          className={`fixed bottom-5 right-5 z-50 rounded-md border px-3 py-2 text-sm shadow-lg ${
            toast.tone === 'ok'
              ? 'border-success/40 bg-success/10 text-success'
              : 'border-danger/40 bg-danger/10 text-danger'
          }`}
        >
          <span className="inline-flex items-center gap-1.5">
            {toast.tone === 'ok'
              ? <CheckCircle2 className="h-3.5 w-3.5" />
              : <AlertTriangle className="h-3.5 w-3.5" />}
            {toast.msg}
          </span>
        </div>
      )}
      <Dialog open={isOpen} onOpenChange={setOpen}>
        <DialogContent className="p-0 max-w-xl overflow-hidden">
          <Command label="Command palette" className="bg-elevated">
            <div className="flex items-center border-b border-border px-3">
              <Sparkles className="h-4 w-4 text-accent" />
              <Command.Input
                value={query}
                onValueChange={setQuery}
                placeholder="Ask, search, or jump to…"
                className="flex h-12 w-full bg-transparent px-3 text-sm outline-none placeholder:text-muted-fg"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.defaultPrevented) {
                    const v = (e.target as HTMLInputElement).value;
                    if (v) ask(v);
                  }
                }}
              />
              {busy && <span className="text-[11px] text-muted-fg pr-2">{busy}…</span>}
            </div>
            <Command.List className="max-h-[60vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-6 text-center text-sm text-muted-fg">
                Press Enter to ask the question.
              </Command.Empty>

              <Command.Group heading="Actions"
                             className="text-[11px] uppercase tracking-wider text-muted-fg px-2 pt-2 pb-1">
                <Item icon={<RefreshCw className="h-4 w-4" />}
                      label="Reindex everything"
                      hint="rebuild Chroma from SQLite (background)"
                      onSelect={() => void actionReindex()} />
                <Item icon={<Star className="h-4 w-4" />}
                      label="Jump to most-cited source"
                      hint="open the file with the most chunks"
                      onSelect={() => void actionJumpToMostCited()} />
                <Item icon={<FileWarning className="h-4 w-4" />}
                      label="Open latest failure"
                      hint="dashboard → pipeline view"
                      onSelect={() => void actionOpenLatestFailure()} />
                <Item icon={<GitFork className="h-4 w-4" />}
                      label="Show contradictions"
                      hint="dashboard → contradictions panel"
                      onSelect={() => void actionShowContradictions()} />
                <Item icon={<AlertTriangle className="h-4 w-4" />}
                      label="Show overdue obligations"
                      hint="dashboard → obligations panel"
                      onSelect={() => void actionShowOverdue()} />
                <Item icon={<FolderInput className="h-4 w-4" />}
                      label="Ingest a folder"
                      hint="opens /import"
                      onSelect={() => go('/import')} />
              </Command.Group>

              <Command.Group heading="Navigate"
                             className="text-[11px] uppercase tracking-wider text-muted-fg px-2 pt-2 pb-1">
                <Item icon={<LayoutDashboard className="h-4 w-4" />} label="Dashboard"
                      onSelect={() => go('/dashboard')} />
                <Item icon={<Search className="h-4 w-4" />} label="Ask & Search"
                      onSelect={() => go('/search')} />
                <Item icon={<Clock className="h-4 w-4" />} label="Timeline"
                      onSelect={() => go('/timeline')} />
                <Item icon={<Upload className="h-4 w-4" />} label="Import"
                      onSelect={() => go('/import')} />
                <Item icon={<SettingsIcon className="h-4 w-4" />} label="Settings"
                      onSelect={() => go('/settings')} />
              </Command.Group>

              <Command.Group heading="Suggestions"
                             className="text-[11px] uppercase tracking-wider text-muted-fg px-2 pt-2 pb-1">
                <Item icon={<MessageSquare className="h-4 w-4" />}
                      label="Did Sequoia change the price?"
                      onSelect={() => ask('Did Sequoia change the price?')} />
                <Item icon={<MessageSquare className="h-4 w-4" />}
                      label="When is delivery due?"
                      onSelect={() => ask('When is delivery due?')} />
                <Item icon={<Hammer className="h-4 w-4" />}
                      label="When was the master agreement signed?"
                      onSelect={() => ask('When was the master agreement signed?')} />
              </Command.Group>
            </Command.List>
          </Command>
        </DialogContent>
      </Dialog>
    </Ctx.Provider>
  );
}

function Item({
  icon, label, hint, onSelect,
}: {
  icon: React.ReactNode;
  label: string;
  hint?: string;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex items-center gap-2 rounded-md px-2 py-2 text-sm text-fg aria-selected:bg-muted cursor-pointer"
    >
      <span className="text-muted-fg">{icon}</span>
      <span className="flex-1 truncate">{label}</span>
      {hint && <span className="text-[11px] text-muted-fg/80 truncate">{hint}</span>}
    </Command.Item>
  );
}
