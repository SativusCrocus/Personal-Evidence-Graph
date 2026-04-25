#!/usr/bin/env python3
"""Seed the local SQLite DB with the same demo dataset the public Vercel
preview shows. Lets you run the project end-to-end against a real backend
without ingesting your own files first.

Usage:
    python scripts/seed_demo.py              # uses EVG_DATA_DIR / .env
    python scripts/seed_demo.py --reset      # wipe demo rows first
    python scripts/seed_demo.py --dry-run    # parse + validate only

The story matches frontend/lib/demo/fixtures.ts:
  - 5 files: master agreement, two invoices, voice memo, shipping receipt
  - 1 contradiction: invoice total changed $4,500 → $5,200
  - 1 obligation: April 15 delivery (now overdue)
  - Pipeline events including one OCR failure + retry on the receipt
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make backend importable when run as a script.
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.deps import get_engine, session_scope  # noqa: E402
from app.models.db import (  # noqa: E402
    Chunk,
    Claim,
    Contradiction,
    File,
    Obligation,
    PipelineEvent,
    TimelineEvent,
)
from app.services.claims import (  # noqa: E402
    create_claim,
    create_contradiction,
    create_obligation,
    record_pipeline_event,
)


# ───────────────────────── data ─────────────────────────


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


FILES = [
    dict(id="f_master_agreement", display_name="sequoia-master-agreement.pdf",
         path="/demo/contracts/sequoia-master-agreement.pdf",
         sha256="demo:master", mime="application/pdf", bytes=184_320,
         source_type="pdf", source_dt=_dt("2026-02-12T00:00:00Z"),
         ingested_at=_dt("2026-02-12T18:04:00Z"), status="indexed"),
    dict(id="f_invoice_march", display_name="sequoia-invoice-march.pdf",
         path="/demo/invoices/sequoia-invoice-march.pdf",
         sha256="demo:inv-mar", mime="application/pdf", bytes=41_988,
         source_type="pdf", source_dt=_dt("2026-03-31T00:00:00Z"),
         ingested_at=_dt("2026-04-01T09:11:00Z"), status="indexed"),
    dict(id="f_invoice_april", display_name="sequoia-invoice-april.pdf",
         path="/demo/invoices/sequoia-invoice-april.pdf",
         sha256="demo:inv-apr", mime="application/pdf", bytes=42_402,
         source_type="pdf", source_dt=_dt("2026-04-21T00:00:00Z"),
         ingested_at=_dt("2026-04-22T08:46:00Z"), status="indexed"),
    dict(id="f_voicememo_call", display_name="vendor-call-2026-04-08.m4a",
         path="/demo/voice/vendor-call-2026-04-08.m4a",
         sha256="demo:voice", mime="audio/mp4", bytes=2_412_113,
         source_type="audio", source_dt=_dt("2026-04-08T16:14:00Z"),
         ingested_at=_dt("2026-04-08T16:33:00Z"), status="indexed"),
    dict(id="f_receipt_shipping", display_name="ups-receipt-2026-04-19.jpg",
         path="/demo/receipts/ups-receipt-2026-04-19.jpg",
         sha256="demo:receipt", mime="image/jpeg", bytes=612_440,
         source_type="image", source_dt=_dt("2026-04-19T00:00:00Z"),
         ingested_at=_dt("2026-04-19T11:02:00Z"), status="indexed"),
]

CHUNKS = [
    dict(id="c_master_1", file_id="f_master_agreement", ord=0, page=1,
         text=("MASTER SERVICES AGREEMENT — Sequoia Print Co. and Owner (the \"Customer\"). "
               "This agreement is entered into on February 12, 2026 and governs all production work "
               "requested by the Customer through the term ending February 11, 2027.")),
    dict(id="c_master_2", file_id="f_master_agreement", ord=1, page=2,
         text=("Section 4.2 — Pricing. Per-unit pricing for standard offset runs shall be locked at "
               "the rates in Schedule A for the duration of the agreement. Any change to the rate "
               "card requires 30 days written notice to the Customer.")),
    dict(id="c_master_3", file_id="f_master_agreement", ord=2, page=4,
         text=("Schedule A: Standard Q1/Q2 production — $4,500 base per monthly run, inclusive of setup, "
               "plates, and one round of revisions. Rush surcharges itemized separately.")),
    dict(id="c_inv_mar_1", file_id="f_invoice_march", ord=0, page=1,
         text=("INVOICE #2026-031 — Sequoia Print Co. Bill date: March 31, 2026. "
               "Standard production run (Schedule A). Subtotal: $4,500.00. Tax: $0.00. Total due: $4,500.00. "
               "Net 30, due April 30, 2026.")),
    dict(id="c_inv_mar_2", file_id="f_invoice_march", ord=1, page=1,
         text=("Line items: 1× monthly offset run, 2,000 units, 4-color, includes plates and one revision. "
               "Per master agreement Schedule A.")),
    dict(id="c_inv_apr_1", file_id="f_invoice_april", ord=0, page=1,
         text=("INVOICE #2026-049 — Sequoia Print Co. Bill date: April 21, 2026. "
               "Standard production run. Subtotal: $5,200.00. Tax: $0.00. Total due: $5,200.00. "
               "Net 30, due May 21, 2026.")),
    dict(id="c_inv_apr_2", file_id="f_invoice_april", ord=1, page=1,
         text=("Line items: 1× monthly offset run, 2,000 units, 4-color, includes plates and one revision. "
               "Per master agreement Schedule A. (No itemized rush surcharge listed.)")),
    dict(id="c_voice_1", file_id="f_voicememo_call", ord=0,
         ts_start_ms=0, ts_end_ms=47_000,
         text=("Owner: Just to confirm — you said the April run will be ready by the 15th, right? "
               "Sequoia rep: Yes, absolutely. We'll have everything packed and out the door by April 15th. "
               "You'll see a UPS tracking number that day.")),
    dict(id="c_voice_2", file_id="f_voicememo_call", ord=1,
         ts_start_ms=47_000, ts_end_ms=92_000,
         text=("Owner: And pricing is the same as last month? Sequoia rep: Same Schedule A pricing, yep. "
               "I'll send the invoice the day we ship.")),
    dict(id="c_receipt_1", file_id="f_receipt_shipping", ord=0,
         text=("UPS Ground Receipt — Tracking 1Z999AA10123456784. Ship date 04/19/2026. "
               "Pickup from Sequoia Print Co, 412 Industrial Way. Total charge $87.40. "
               "Delivery est. 04/22/2026.")),
]

# Claims — excerpts must verbatim-match a substring of the corresponding chunk.
CLAIMS = [
    dict(id="cl_delivery_april_15",
         text="Sequoia Print Co will deliver the April production run by April 15, 2026.",
         status="supported", confidence=0.92,
         source_chunk_id="c_voice_1", source_file_id="f_voicememo_call",
         source_excerpt="We'll have everything packed and out the door by April 15th.",
         source_dt=_dt("2026-04-08T16:14:00Z"),
         obligation_id="ob_delivery_april_15"),
    dict(id="cl_invoice_march_total",
         text="March invoice total is $4,500.00.",
         status="contradicted", confidence=0.99,
         source_chunk_id="c_inv_mar_1", source_file_id="f_invoice_march",
         source_excerpt="Subtotal: $4,500.00. Tax: $0.00. Total due: $4,500.00.",
         source_dt=_dt("2026-03-31T00:00:00Z"),
         contradiction_id="cn_invoice_total_changed"),
    dict(id="cl_invoice_april_total",
         text="April invoice total is $5,200.00.",
         status="contradicted", confidence=0.99,
         source_chunk_id="c_inv_apr_1", source_file_id="f_invoice_april",
         source_excerpt="Subtotal: $5,200.00. Tax: $0.00. Total due: $5,200.00.",
         source_dt=_dt("2026-04-21T00:00:00Z"),
         contradiction_id="cn_invoice_total_changed"),
    dict(id="cl_master_signed",
         text="Master Services Agreement with Sequoia Print Co was signed February 12, 2026.",
         status="supported", confidence=0.97,
         source_chunk_id="c_master_1", source_file_id="f_master_agreement",
         source_excerpt="This agreement is entered into on February 12, 2026 and governs all production work",
         source_dt=_dt("2026-02-12T00:00:00Z")),
    dict(id="cl_shipping_total",
         text="Shipping for the April production cost $87.40 (UPS Ground).",
         status="supported", confidence=0.84,
         source_chunk_id="c_receipt_1", source_file_id="f_receipt_shipping",
         source_excerpt="Total charge $87.40.",
         source_dt=_dt("2026-04-19T00:00:00Z")),
]

CONTRADICTIONS = [
    dict(id="cn_invoice_total_changed",
         topic="Monthly invoice total",
         summary=("Sequoia Print Co billed $4,500 in March and $5,200 in April for an identical "
                  "line item (1× monthly offset run, 2,000 units, 4-color, Schedule A). The master "
                  "agreement requires 30 days written notice for any rate change — no such notice "
                  "is on file."),
         severity="high",
         detected_at=_dt("2026-04-22T08:46:14Z"),
         claim_ids=["cl_invoice_march_total", "cl_invoice_april_total"],
         related_chunk_ids=["c_master_2", "c_master_3"]),
]

OBLIGATIONS = [
    dict(id="ob_delivery_april_15",
         text="Sequoia Print Co to deliver April production run",
         counterparty="Sequoia Print Co",
         direction="incoming",
         due_at=_dt("2026-04-15T23:59:00Z"),
         status="overdue",
         claim_id="cl_delivery_april_15",
         source_chunk_id="c_voice_1",
         source_file_id="f_voicememo_call",
         source_excerpt="We'll have everything packed and out the door by April 15th."),
]

TIMELINE = [
    dict(id="t_master_signed", file_id="f_master_agreement", chunk_id="c_master_1",
         occurred_at=_dt("2026-02-12T00:00:00Z"),
         title="Master Services Agreement signed with Sequoia Print Co",
         description="Annual MSA, term ending Feb 11 2027. Schedule A pricing locked.",
         kind="agreement", confidence=0.97),
    dict(id="t_invoice_march", file_id="f_invoice_march", chunk_id="c_inv_mar_1",
         occurred_at=_dt("2026-03-31T00:00:00Z"),
         title="Sequoia invoice #2026-031 — $4,500.00",
         description="Standard monthly run, Schedule A pricing.",
         kind="invoice", confidence=0.99),
    dict(id="t_call_april", file_id="f_voicememo_call", chunk_id="c_voice_1",
         occurred_at=_dt("2026-04-08T16:14:00Z"),
         title="Phone call with Sequoia — delivery confirmed for April 15",
         description="Vendor confirms April production ships by 4/15. Same Schedule A pricing.",
         kind="call", confidence=0.92),
    dict(id="t_deadline_april_15", file_id="f_voicememo_call", chunk_id="c_voice_1",
         occurred_at=_dt("2026-04-15T23:59:00Z"),
         title="Deadline — April production run delivery",
         description="Promised by Sequoia rep on the 04/08 call. Linked obligation.",
         kind="deadline", confidence=0.92),
    dict(id="t_shipping", file_id="f_receipt_shipping", chunk_id="c_receipt_1",
         occurred_at=_dt("2026-04-19T00:00:00Z"),
         title="UPS pickup from Sequoia — $87.40",
         description="Tracking 1Z999AA10123456784. Shipped 4 days after promised delivery.",
         kind="shipment", confidence=0.84),
    dict(id="t_invoice_april", file_id="f_invoice_april", chunk_id="c_inv_apr_1",
         occurred_at=_dt("2026-04-21T00:00:00Z"),
         title="Sequoia invoice #2026-049 — $5,200.00",
         description="Same line items as March. Total increased $700. No 30-day notice on file.",
         kind="invoice", confidence=0.99),
]

# Pipeline events: standard 7-stage flow per file; the receipt has an OCR
# failure-then-retry to demonstrate the operational view.
STAGES = ["received", "hashed", "extracted", "chunked", "embedded", "indexed", "queryable"]


def _make_pipeline(file_id: str, started_at: datetime,
                   failed_stages: dict[str, str] | None = None) -> list[dict]:
    failed_stages = failed_stages or {}
    out: list[dict] = []
    cursor = started_at.timestamp()
    for stage in STAGES:
        cursor += 1.2
        if stage in failed_stages:
            out.append(dict(
                id=f"{file_id}_{stage}_failed", file_id=file_id, stage=stage,
                status="failed",
                at=datetime.fromtimestamp(cursor, tz=timezone.utc),
                message=failed_stages[stage],
            ))
            cursor += 1.5
            out.append(dict(
                id=f"{file_id}_{stage}_retried", file_id=file_id, stage=stage,
                status="retried",
                at=datetime.fromtimestamp(cursor, tz=timezone.utc),
                message="Retried with PaddleOCR fallback",
            ))
            cursor += 1.2
        out.append(dict(
            id=f"{file_id}_{stage}", file_id=file_id, stage=stage,
            status="success",
            at=datetime.fromtimestamp(cursor, tz=timezone.utc),
        ))
    return out


PIPELINE: list[dict] = []
PIPELINE += _make_pipeline("f_master_agreement", _dt("2026-02-12T18:04:00Z"))
PIPELINE += _make_pipeline("f_invoice_march", _dt("2026-04-01T09:11:00Z"))
PIPELINE += _make_pipeline("f_invoice_april", _dt("2026-04-22T08:46:00Z"))
PIPELINE += _make_pipeline("f_voicememo_call", _dt("2026-04-08T16:33:00Z"))
PIPELINE += _make_pipeline(
    "f_receipt_shipping",
    _dt("2026-04-19T11:02:00Z"),
    failed_stages={"extracted": "Tesseract: low-confidence regions, 0.41 mean conf"},
)


# ───────────────────────── seed ─────────────────────────


DEMO_FILE_IDS = {f["id"] for f in FILES}


def _wipe(db) -> None:
    db.query(PipelineEvent).filter(PipelineEvent.file_id.in_(DEMO_FILE_IDS)).delete(
        synchronize_session=False
    )
    db.query(Obligation).filter(Obligation.source_file_id.in_(DEMO_FILE_IDS)).delete(
        synchronize_session=False
    )
    db.query(Contradiction).filter(
        Contradiction.id.in_([c["id"] for c in CONTRADICTIONS])
    ).delete(synchronize_session=False)
    db.query(Claim).filter(Claim.source_file_id.in_(DEMO_FILE_IDS)).delete(
        synchronize_session=False
    )
    db.query(TimelineEvent).filter(TimelineEvent.file_id.in_(DEMO_FILE_IDS)).delete(
        synchronize_session=False
    )
    db.query(Chunk).filter(Chunk.file_id.in_(DEMO_FILE_IDS)).delete(
        synchronize_session=False
    )
    db.query(File).filter(File.id.in_(DEMO_FILE_IDS)).delete(synchronize_session=False)
    db.flush()


def seed(*, reset: bool, dry_run: bool) -> None:
    get_engine()  # bootstrap schema if needed
    with session_scope() as db:
        if reset:
            _wipe(db)
        # Files
        for f in FILES:
            if db.get(File, f["id"]) is None:
                db.add(File(**f))
        # Chunks
        for c in CHUNKS:
            if db.get(Chunk, c["id"]) is None:
                db.add(Chunk(**c))
        db.flush()

        # Timeline
        for ev in TIMELINE:
            if db.get(TimelineEvent, ev["id"]) is None:
                db.add(TimelineEvent(**ev))

        # Claims (citation contract enforced by create_claim)
        for cl in CLAIMS:
            if db.get(Claim, cl["id"]) is not None:
                continue
            create_claim(db, claim_id=cl["id"], **{k: v for k, v in cl.items() if k != "id"})

        # Contradictions
        for cn in CONTRADICTIONS:
            if db.get(Contradiction, cn["id"]) is not None:
                continue
            create_contradiction(
                db,
                contradiction_id=cn["id"],
                topic=cn["topic"],
                summary=cn["summary"],
                severity=cn["severity"],
                claim_ids=cn["claim_ids"],
                related_chunk_ids=cn["related_chunk_ids"],
                detected_at=cn["detected_at"],
            )

        # Obligations
        for ob in OBLIGATIONS:
            if db.get(Obligation, ob["id"]) is not None:
                continue
            create_obligation(
                db,
                obligation_id=ob["id"],
                **{k: v for k, v in ob.items() if k != "id"},
            )

        # Pipeline events
        for pe in PIPELINE:
            if db.get(PipelineEvent, pe["id"]) is not None:
                continue
            record_pipeline_event(
                db,
                event_id=pe["id"],
                file_id=pe["file_id"],
                stage=pe["stage"],
                status=pe["status"],
                message=pe.get("message"),
                at=pe["at"],
            )

        if dry_run:
            db.rollback()
            print("dry-run: rolled back, nothing persisted")
            return

    print(
        f"seeded: {len(FILES)} files · {len(CHUNKS)} chunks · {len(CLAIMS)} claims · "
        f"{len(CONTRADICTIONS)} contradiction · {len(OBLIGATIONS)} obligation · "
        f"{len(TIMELINE)} timeline · {len(PIPELINE)} pipeline events"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed the local DB with the PEG demo dataset.")
    ap.add_argument("--reset", action="store_true", help="delete demo rows before seeding")
    ap.add_argument("--dry-run", action="store_true", help="validate without persisting")
    args = ap.parse_args()
    seed(reset=args.reset, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
