'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Search, LayoutDashboard, Clock, Upload, Settings as SettingsIcon, Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const links = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/search', label: 'Ask & Search', icon: Search },
  { href: '/timeline', label: 'Timeline', icon: Clock },
  { href: '/import', label: 'Import', icon: Upload },
  { href: '/settings', label: 'Settings', icon: SettingsIcon },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 px-5 h-14 border-b border-border">
        <div className="h-7 w-7 rounded-md bg-accent/15 grid place-items-center">
          <Sparkles className="h-4 w-4 text-accent" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">Evidence Graph</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-fg">local-first</div>
        </div>
      </div>

      <nav className="flex flex-col gap-0.5 p-3">
        {links.map(({ href, label, icon: Icon }) => {
          const active = path === href || path?.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-accent/10 text-accent'
                  : 'text-muted-fg hover:bg-muted hover:text-fg'
              )}
            >
              <Icon className={cn('h-4 w-4', active ? 'text-accent' : 'text-muted-fg group-hover:text-fg')} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto p-3 text-[11px] text-muted-fg">
        <div className="rounded-md border border-border bg-elevated px-3 py-2">
          <div className="font-medium text-fg">Search Your Life.</div>
          <div>Prove Everything.</div>
        </div>
      </div>
    </aside>
  );
}
