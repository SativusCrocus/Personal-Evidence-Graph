from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _client():
    from app.main import create_app
    return TestClient(create_app())


def test_health_endpoint_returns_status():
    c = _client()
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body and "db" in body and "chroma" in body and "ollama" in body
    assert body["db"] is True
    assert body["chroma"] is True


def test_root_endpoint():
    c = _client()
    r = c.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "personal-evidence-graph"


def test_ingest_text_via_http():
    c = _client()
    body = b"Project Alpha kickoff is scheduled for 2025-03-01. Budget is $12,000."
    files = {"upload": ("alpha.txt", io.BytesIO(body), "text/plain")}
    r = c.post("/ingest/file", files=files)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["status"] == "indexed"
    assert payload["file_id"]


def test_ingest_clipboard_via_http():
    c = _client()
    r = c.post("/ingest/clipboard", json={
        "text": "Saw a draft proposal on 2025-04-01. Pricing line item: $9,400.",
        "source": "browser",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "indexed"


def test_query_with_no_data_returns_refusal():
    c = _client()
    r = c.post("/query", json={"question": "Truly unrelated question about quantum spam."})
    assert r.status_code == 200
    body = r.json()
    assert body["refused"] is True
    assert body["answer"] == "No supporting evidence found."
    assert body["citations"] == []


def test_folder_ingest_rejects_outside_root(tmp_path):
    c = _client()
    r = c.post("/ingest/folder", json={"path": "/etc"})
    assert r.status_code == 400


def test_security_headers_present():
    c = _client()
    r = c.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
