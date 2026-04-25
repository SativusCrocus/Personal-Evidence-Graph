#!/usr/bin/env python3
"""Backfill the claims table for files already in the local DB.

Useful when you've ingested a corpus before the extractor existed, or when
you want to re-run extraction with a different LLM. Skips chunks that
already have at least one claim; pass --force to re-extract those too.

Usage:
    python scripts/extract_claims.py                  # all files
    python scripts/extract_claims.py --file <id>      # one file
    python scripts/extract_claims.py --status indexed # only indexed files
    python scripts/extract_claims.py --force          # ignore existing claims
    python scripts/extract_claims.py --dry-run        # parse only, no writes
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
from app.services.claim_extraction import extract_for_file  # noqa: E402


async def _run(file_ids: list[str], *, force: bool) -> int:
    s = get_settings()
    total_created = 0
    total_failed = 0
    for fid in file_ids:
        result = await extract_for_file(
            fid, settings=s, skip_if_already_extracted=not force,
        )
        print(
            f"  {fid}: created={result.claims_created} "
            f"dropped={result.claims_dropped_invalid} failed={result.chunks_failed} "
            f"({result.elapsed_ms}ms)"
        )
        total_created += result.claims_created
        total_failed += result.chunks_failed
    print(f"\nDone. {total_created} claim(s) created across {len(file_ids)} file(s); "
          f"{total_failed} chunk failures.")
    return 0 if total_failed == 0 else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill claim extraction.")
    ap.add_argument("--file", action="append", default=[],
                    help="explicit file id (may repeat). default: all files")
    ap.add_argument("--status", default="indexed",
                    help="filter files by status (default: indexed)")
    ap.add_argument("--force", action="store_true",
                    help="re-extract chunks that already have claims")
    ap.add_argument("--dry-run", action="store_true",
                    help="rollback after extraction (no claims persisted)")
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

    print(f"Extracting claims for {len(file_ids)} file(s) "
          f"(force={args.force}, dry_run={args.dry_run})…")

    if args.dry_run:
        # Use a savepoint we'll never commit by running inside a transaction
        # we explicitly roll back. The extractor uses session_scope() per
        # batch internally, so the simplest dry-run is to run it and then
        # delete the new rows. Cheap, and readable.
        from app.models.db import Claim
        before = _claim_ids_set()
        rc = asyncio.run(_run(file_ids, force=args.force))
        with session_scope() as db:
            new_ids = _claim_ids_set() - before
            if new_ids:
                db.query(Claim).filter(Claim.id.in_(new_ids)).delete(synchronize_session=False)
        print(f"dry-run: rolled back {len(new_ids)} new claim row(s).")
        return rc

    return asyncio.run(_run(file_ids, force=args.force))


def _claim_ids_set() -> set[str]:
    from app.models.db import Claim
    with session_scope() as db:
        return {cid for (cid,) in db.query(Claim.id).all()}


if __name__ == "__main__":
    raise SystemExit(main())
