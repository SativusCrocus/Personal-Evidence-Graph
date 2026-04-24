'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { api, type AnswerResponse } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { CitationList } from '@/components/citation-list';
import { cn, formatMs } from '@/lib/utils';

export function AnswerPanel({ initialQuestion = '' }: { initialQuestion?: string }) {
  const [q, setQ] = React.useState(initialQuestion);
  const [loading, setLoading] = React.useState(false);
  const [answer, setAnswer] = React.useState<AnswerResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (initialQuestion) void ask(initialQuestion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  async function ask(question: string) {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const res = await api.query(question.trim());
      setAnswer(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'request failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(q);
        }}
        className="flex gap-2"
      >
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder='Try: "Did the client approve the pricing?" or "When did I promise delivery?"'
          className="text-base h-11"
          autoFocus
        />
        <Button type="submit" size="lg" disabled={loading || !q.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Ask'}
        </Button>
      </form>

      <AnimatePresence mode="wait">
        {error && (
          <motion.div
            key="err"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <Card className="border-danger/50 bg-danger/5">
              <CardContent className="p-4 flex items-start gap-2 text-sm text-danger">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {loading && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="space-y-3"
          >
            <Card>
              <CardContent className="p-5 space-y-3">
                <SkeletonLine width="35%" />
                <SkeletonLine width="80%" />
                <SkeletonLine width="65%" />
              </CardContent>
            </Card>
          </motion.div>
        )}

        {answer && !loading && (
          <motion.div
            key={answer.answer + answer.latency_ms}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="grid lg:grid-cols-[1fr_minmax(360px,_440px)] gap-5"
          >
            <Card className={cn(answer.refused && 'border-warning/50 bg-warning/5')}>
              <CardContent className="p-5 space-y-3">
                <div className="flex items-center gap-2">
                  {answer.refused ? (
                    <AlertTriangle className="h-4 w-4 text-warning" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  )}
                  <span className="text-xs uppercase tracking-wider text-muted-fg">
                    {answer.refused ? 'No evidence' : 'Answer'}
                  </span>
                  <div className="ml-auto flex items-center gap-2">
                    <Badge variant={answer.confidence > 0.6 ? 'success' : answer.confidence > 0.3 ? 'warning' : 'default'}>
                      conf {Math.round(answer.confidence * 100)}%
                    </Badge>
                    <Badge>{formatMs(answer.latency_ms)}</Badge>
                  </div>
                </div>
                <p className="text-base leading-relaxed text-fg whitespace-pre-wrap">
                  {answer.answer}
                </p>
              </CardContent>
            </Card>
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-wider text-muted-fg px-1">
                Evidence ({answer.citations.length})
              </div>
              <CitationList citations={answer.citations} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SkeletonLine({ width }: { width: string }) {
  return (
    <div className="h-3 rounded bg-muted overflow-hidden relative">
      <span className="absolute inset-y-0 left-0 bg-muted-fg/10" style={{ width }} />
    </div>
  );
}
