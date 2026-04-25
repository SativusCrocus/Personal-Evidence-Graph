#!/usr/bin/env python3
"""Backfill obligations for files that already have claims.

Walks the supported claims for each selected file, asks the local LLM
whether each one is a commitment with a specific counterparty + due date,
and persists Obligation rows + back-links on the Claim. Skips claims that
are already linked to an obligation unless --force is passed.

Usage:
    python scripts/extract_obligations.py
    python scripts/extract_obligations.py --file <file_id>
    python scripts/extract_obligations.py --status indexed
    python scripts/extract_obligations.py --force
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
from app.services.obligation_extraction import extract_for_file  # noqa: E402


async def _run(file_ids: list[str], *, force: bool) -> int:
    s = get_settings()
    total_created = 0
    total_errors = 0
    for fid in file_ids:
        result = await extract_for_file(
            fid, settings=s, skip_already_linked=not force,
        )
        print(
            f"  {fid}: created={result.obligations_created} "
            f"rejected={result.rejected_invalid} errors={result.claim_errors} "
            f"({result.elapsed_ms}ms)"
        )
        total_created += result.obligations_created
        total_errors += result.claim_errors
    print(
        f"\nDone. {total_created} obligation(s) created across {len(file_ids)} file(s); "
        f"{total_errors} claim errors."
    )
    return 0 if total_errors == 0 else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill obligation extraction.")
    ap.add_argument("--file", action="append", default=[],
                    help="explicit file id (may repeat). default: all files")
    ap.add_argument("--status", default="indexed",
                    help="filter files by status (default: indexed)")
    ap.add_argument("--force", action="store_true",
                    help="re-extract claims that are already linked to an obligation")
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

    print(f"Extracting obligations for {len(file_ids)} file(s) (force={args.force})…")
    return asyncio.run(_run(file_ids, force=args.force))


if __name__ == "__main__":
    raise SystemExit(main())
