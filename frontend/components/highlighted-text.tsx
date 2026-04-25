'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Render `text` with each `excerpt` highlighted.
 *
 * Matching is whitespace-tolerant and case-insensitive — the same rules
 * the backend's claim citation contract uses (see
 * backend/app/services/claims.py::excerpt_in_chunk). If an excerpt isn't
 * present, it's skipped silently rather than falsely highlighting prose.
 *
 * Overlapping excerpts are merged into a single highlight span.
 */
export function HighlightedText({
  text,
  excerpts,
  className,
}: {
  text: string;
  excerpts: string[];
  className?: string;
}) {
  const ranges = React.useMemo(() => mergeRanges(findRanges(text, excerpts)), [text, excerpts]);
  if (ranges.length === 0) {
    return <p className={cn('whitespace-pre-wrap leading-relaxed text-fg/90', className)}>{text}</p>;
  }
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  ranges.forEach(([start, end], i) => {
    if (cursor < start) parts.push(text.slice(cursor, start));
    parts.push(
      <mark
        key={i}
        className="rounded px-0.5 bg-accent/20 text-accent ring-1 ring-accent/30"
      >
        {text.slice(start, end)}
      </mark>,
    );
    cursor = end;
  });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return (
    <p className={cn('whitespace-pre-wrap leading-relaxed text-fg/90', className)}>{parts}</p>
  );
}

// ───────────────────────── matcher ─────────────────────────

function findRanges(text: string, excerpts: string[]): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  // Build a normalized lowercase text and an index map back to original offsets.
  const { norm, map } = normalizeWithMap(text);
  for (const raw of excerpts) {
    if (!raw || !raw.trim()) continue;
    const needle = normalize(raw);
    if (!needle) continue;
    let i = 0;
    while (true) {
      const idx = norm.indexOf(needle, i);
      if (idx === -1) break;
      const startOrig = map[idx];
      const endNormIdx = idx + needle.length - 1;
      if (endNormIdx >= map.length) break;
      const endOrig = map[endNormIdx] + 1; // inclusive → exclusive
      out.push([startOrig, endOrig]);
      i = idx + needle.length;
    }
  }
  out.sort((a, b) => a[0] - b[0]);
  return out;
}

function mergeRanges(ranges: Array<[number, number]>): Array<[number, number]> {
  if (ranges.length === 0) return ranges;
  const out: Array<[number, number]> = [ranges[0]];
  for (let i = 1; i < ranges.length; i++) {
    const last = out[out.length - 1];
    const [s, e] = ranges[i];
    if (s <= last[1]) last[1] = Math.max(last[1], e);
    else out.push([s, e]);
  }
  return out;
}

/** Normalize whitespace + case the way the backend does. */
function normalize(s: string): string {
  return s.replace(/\s+/g, ' ').trim().toLowerCase();
}

/** Same normalization, but produce an index map back to the original string. */
function normalizeWithMap(s: string): { norm: string; map: number[] } {
  const norm: string[] = [];
  const map: number[] = [];
  let prevWs = true; // collapse leading whitespace too
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (/\s/.test(ch)) {
      if (!prevWs) {
        norm.push(' ');
        map.push(i);
        prevWs = true;
      }
    } else {
      norm.push(ch.toLowerCase());
      map.push(i);
      prevWs = false;
    }
  }
  // Trim trailing space (keeping map aligned).
  while (norm.length && norm[norm.length - 1] === ' ') {
    norm.pop();
    map.pop();
  }
  return { norm: norm.join(''), map };
}
