"""End-to-end checks for the claim engine endpoints. Uses the demo seed
script so the whole story (vendor + contradiction + obligation + pipeline
events with an OCR retry) lands in a real isolated test DB.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from scripts import seed_demo  # type: ignore[attr-defined]


def _client_with_seed():
    seed_demo.seed(reset=True, dry_run=False)
    from app.main import create_app
    return TestClient(create_app())


def test_claims_endpoint_returns_seeded_rows():
    c = _client_with_seed()
    r = c.get("/claims")
    assert r.status_code == 200, r.text
    rows = r.json()
    ids = {row["id"] for row in rows}
    assert {"cl_delivery_april_15", "cl_invoice_march_total", "cl_invoice_april_total"} <= ids
    # Linked obligation/contradiction roundtrip:
    delivery = next(x for x in rows if x["id"] == "cl_delivery_april_15")
    assert delivery["status"] == "supported"
    assert delivery["obligation_id"] == "ob_delivery_april_15"


def test_claims_filtered_by_status():
    c = _client_with_seed()
    r = c.get("/claims", params={"status": "contradicted"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 2
    assert all(row["status"] == "contradicted" for row in rows)


def test_claims_filtered_by_chunk_id():
    c = _client_with_seed()
    # Voice memo chunk c_voice_1 grounds the delivery claim and only that one.
    r = c.get("/claims", params={"chunk_id": "c_voice_1"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == "cl_delivery_april_15"
    assert rows[0]["source_chunk_id"] == "c_voice_1"

    # A chunk with no claims yields an empty list, not a 404.
    r2 = c.get("/claims", params={"chunk_id": "c_nonexistent"})
    assert r2.status_code == 200
    assert r2.json() == []


def test_contradictions_returns_invoice_total_change():
    c = _client_with_seed()
    r = c.get("/contradictions")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    only = rows[0]
    assert only["severity"] == "high"
    assert only["topic"] == "Monthly invoice total"
    # JSON-encoded id arrays were re-hydrated by the service:
    assert "cl_invoice_march_total" in only["claim_ids"]
    assert "cl_invoice_april_total" in only["claim_ids"]


def test_obligations_endpoint_marks_overdue():
    c = _client_with_seed()
    r = c.get("/obligations")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["counterparty"] == "Sequoia Print Co"
    assert rows[0]["status"] == "overdue"


def test_pipeline_events_include_failed_and_retried_for_receipt():
    c = _client_with_seed()
    r = c.get("/pipeline/events", params={"file_id": "f_receipt_shipping"})
    assert r.status_code == 200, r.text
    rows = r.json()
    statuses = {row["status"] for row in rows}
    assert {"success", "failed", "retried"} <= statuses
    # Final stage reached:
    queryable_success = [r for r in rows if r["stage"] == "queryable" and r["status"] == "success"]
    assert queryable_success, "receipt should still reach the queryable stage after retry"


def test_seed_is_idempotent():
    seed_demo.seed(reset=True, dry_run=False)
    seed_demo.seed(reset=False, dry_run=False)  # second pass must not raise
    from app.main import create_app
    c = TestClient(create_app())
    assert len(c.get("/claims").json()) == 5
    assert len(c.get("/contradictions").json()) == 1
    assert len(c.get("/obligations").json()) == 1
