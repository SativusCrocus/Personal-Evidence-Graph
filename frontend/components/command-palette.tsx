'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Command } from 'cmdk';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { LayoutDashboard, Search, Clock, Upload, Settings as SettingsIcon, Sparkles } from 'lucide-react';

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

  const ctx: PaletteCtx = {
    open: () => setOpen(true),
    close: () => setOpen(false),
    isOpen,
  };

  function go(href: string) { setOpen(false); router.push(href); }
  function ask(q: string) {
    if (!q.trim()) return;
    setOpen(false);
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  return (
    <Ctx.Provider value={ctx}>
      {children}
      <Dialog open={isOpen} onOpenChange={setOpen}>
        <DialogContent className="p-0 max-w-xl overflow-hidden">
          <Command label="Command palette" className="bg-elevated">
            <div className="flex items-center border-b border-border px-3">
              <Sparkles className="h-4 w-4 text-accent" />
              <Command.Input
                placeholder="Ask, search, or jump to…"
                className="flex h-12 w-full bg-transparent px-3 text-sm outline-none placeholder:text-muted-fg"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const v = (e.target as HTMLInputElement).value;
                    if (v) ask(v);
                  }
                }}
              />
            </div>
            <Command.List className="max-h-[60vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-6 text-center text-sm text-muted-fg">
                Press Enter to ask the question.
              </Command.Empty>
              <Command.Group heading="Navigate" className="text-[11px] uppercase tracking-wider text-muted-fg px-2 pt-2 pb-1">
                <Item icon={<LayoutDashboard className="h-4 w-4" />} label="Dashboard" onSelect={() => go('/dashboard')} />
                <Item icon={<Search className="h-4 w-4" />} label="Ask & Search" onSelect={() => go('/search')} />
                <Item icon={<Clock className="h-4 w-4" />} label="Timeline" onSelect={() => go('/timeline')} />
                <Item icon={<Upload className="h-4 w-4" />} label="Import" onSelect={() => go('/import')} />
                <Item icon={<SettingsIcon className="h-4 w-4" />} label="Settings" onSelect={() => go('/settings')} />
              </Command.Group>
            </Command.List>
          </Command>
        </DialogContent>
      </Dialog>
    </Ctx.Provider>
  );
}

function Item({ icon, label, onSelect }: { icon: React.ReactNode; label: string; onSelect: () => void }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex items-center gap-2 rounded-md px-2 py-2 text-sm text-fg aria-selected:bg-muted cursor-pointer"
    >
      <span className="text-muted-fg">{icon}</span>
      {label}
    </Command.Item>
  );
}
