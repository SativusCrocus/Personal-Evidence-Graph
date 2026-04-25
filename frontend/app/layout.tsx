import './globals.css';
import type { Metadata } from 'next';
import { Sidebar } from '@/components/sidebar';
import { Topbar } from '@/components/topbar';
import { CommandPaletteProvider } from '@/components/command-palette';
import { DemoBanner } from '@/components/demo-banner';
import { TrustStrip } from '@/components/trust-strip';

export const metadata: Metadata = {
  title: 'Personal Evidence Graph — Search Your Life. Prove Everything.',
  description: 'Local-first proof-aware memory system. No data leaves your machine.',
  icons: { icon: '/favicon.svg' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-bg text-fg">
        <CommandPaletteProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex-1 min-w-0 flex flex-col">
              <Topbar />
              <DemoBanner />
              <TrustStrip />
              <main className="flex-1 px-4 md:px-8 py-6 md:py-8 max-w-[1400px] w-full mx-auto">
                {children}
              </main>
            </div>
          </div>
        </CommandPaletteProvider>
      </body>
    </html>
  );
}
