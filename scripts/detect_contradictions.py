#!/usr/bin/env python3
"""Backfill contradiction detection across the existing claim corpus.

For each selected file, runs the same detector that ingestion uses:
embed all claims, K-NN per claim from the file, LLM-judges each
candidate pair, and persists confirmed contradictions (idempotent).

Usage:
    python scripts/detect_contradictions.py
    python scripts/detect_contradictions.py --file <file_id>
    python scripts/detect_contradictions.py --status indexed
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.deps import get_engine, session_scope  # noqa: E402
from app.models.db import File  # noqa: E402
from app.services.contradiction_detection import detect_for_file  # noqa: E402


async def _run(file_ids: list[str]) -> int:
    s = get_settings()
    total_created = 0
    total_dups = 0
    total_errors = 0
    for fid in file_ids:
        result = await detect_for_file(fid, settings=s)
        print(
            f"  {fid}: created={result.contradictions_created} "
            f"dup_skipped={result.duplicates_skipped} "
            f"pairs={result.candidate_pairs} judged={result.pairs_judged} "
            f"errors={result.pair_errors} ({result.elapsed_ms}ms)"
        )
        total_created += result.contradictions_created
        total_dups += result.duplicates_skipped
        total_errors += result.pair_errors
    print(
        f"\nDone. {total_created} new contradiction(s), "
        f"{total_dups} duplicates skipped, "
        f"{total_errors} pair errors across {len(file_ids)} file(s)."
    )
    return 0 if total_errors == 0 else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill contradiction detection.")
    ap.add_argument("--file", action="append", default=[],
                    help="explicit file id (may repeat). default: all files")
    ap.add_argument("--status", default="indexed",
                    help="filter files by status (default: indexed)")
    args = ap.parse_args()

    get_engine()  # bootstrap

    if args.file:
        file_ids = list(args.file)
    else:
        with session_scope() as db:
            file_ids = [
                fid for (fid,) in db.query(File.id).filter(File.status == args.status).all()
            ]
        if not file_ids:
            print(f"No files with status={args.status} found.")
            return 0

    print(f"Detecting contradictions for {len(file_ids)} file(s)…")
    return asyncio.run(_run(file_ids))


if __name__ == "__main__":
    raise SystemExit(main())
