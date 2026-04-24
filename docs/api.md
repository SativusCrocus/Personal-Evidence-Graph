# API Reference

Base URL: `http://127.0.0.1:8000`. Interactive docs at `/docs`.

## Health

### `GET /health`
```json
{
  "ok": true,
  "version": "0.1.0",
  "db": true,
  "chroma": true,
  "ollama": true,
  "embed_model": "BAAI/bge-small-en-v1.5",
  "llm_model": "llama3.1:8b"
}
```

## Ingestion

### `POST /ingest/file`  (multipart/form-data)
Body: `upload` field (file). Returns:
```json
{ "file_id": "...", "sha256": "...", "status": "indexed", "duplicate": false }
```
Rate-limited 60/min. Max size: `EVG_MAX_UPLOAD_MB`.

### `POST /ingest/folder`
```json
{ "path": "/Users/you/Documents/contracts", "recursive": true }
```
Walks the path and ingests every file. Returns an array of `IngestResponse`.
Path must lie under `EVG_WATCHED_ROOTS` or `EVG_DATA_DIR`. Rejected with 400 otherwise.

### `POST /ingest/clipboard`
```json
{ "text": "Snippet text…", "source": "browser-tab", "occurred_at": "2025-04-12T10:00:00Z" }
```

## Query

### `POST /query`
```json
{
  "question": "Did the client approve the pricing?",
  "k": 8,
  "source_types": ["pdf", "text"],
  "date_from": "2025-01-01T00:00:00Z",
  "date_to":   "2025-06-01T00:00:00Z"
}
```
Response:
```json
{
  "answer": "...",
  "citations": [
    {
      "chunk_id": "...",
      "file_id": "...",
      "file_name": "contract.pdf",
      "file_path": "/.../contract.pdf",
      "source_type": "pdf",
      "source_dt": "2025-01-04T10:00:00Z",
      "page": 3,
      "ts_start_ms": null,
      "ts_end_ms": null,
      "excerpt": "...",
      "score": 0.81
    }
  ],
  "confidence": 0.78,
  "refused": false,
  "latency_ms": 814
}
```

If retrieval is empty or the LLM output fails the citation contract:
```json
{ "answer": "No supporting evidence found.", "citations": [], "confidence": 0.0, "refused": true, "latency_ms": 31 }
```

### `POST /query/stream`  (SSE)
Same body. Emits Server-Sent Events:
- `event: retrieval` — `{ count, chunk_ids }`
- `event: token`     — `{ text }` (model output token; raw JSON is buffered, not parsed)
- `event: final`     — `{ payload: AnswerResponse }`

## Timeline

### `GET /timeline?from=&to=&kind=&q=&limit=200&offset=0`
Returns chronologically sorted timeline events derived from enrichments + file dates.

## Evidence

### `GET /evidence/{chunk_id}`
Returns the chunk, its parent file, neighboring chunks, and any enrichments.

### `GET /evidence/file/{file_id}/raw`
Streams the raw file from disk. Used by the split-pane preview.

## Files

### `GET /files?status=&source_type=&q=&limit=&offset=`
Lists ingested files with chunk counts.

### `GET /files/{file_id}`
Single file summary.

### `DELETE /files/{file_id}`
Cascades chunks + enrichments + timeline events; removes vectors from Chroma.

### `GET /files/_/stats`
Aggregate counts for the dashboard:
```json
{
  "files": 132, "chunks": 4189, "timeline_events": 215,
  "queries": 47, "refused": 3,
  "by_source_type": { "pdf": 42, "text": 60, "image": 18, "audio": 12 }
}
```

## Admin

### `POST /reindex`
Queues a background rebuild of the Chroma collection from SQLite. Idempotent.
