'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { AnswerPanel } from '@/components/answer-panel';

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}

function Inner() {
  const params = useSearchParams();
  const initial = params.get('q') ?? '';
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Ask & Search</h1>
        <p className="text-sm text-muted-fg">
          Every answer must cite at least one piece of evidence. If nothing matches, you'll see <em>“No supporting evidence found.”</em>
        </p>
      </header>
      <AnswerPanel initialQuestion={initial} />
    </div>
  );
}
