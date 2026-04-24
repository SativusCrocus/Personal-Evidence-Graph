# Architecture

```
                    ┌──────────────────────┐
                    │  Next.js 15 frontend │
                    │  (localhost:3000)    │
                    └──────────┬───────────┘
                               │ fetch / SSE / multipart
                    ┌──────────▼───────────┐
                    │  FastAPI backend     │
                    │  (localhost:8000)    │
                    └──┬────┬────┬─────┬───┘
         ingestion ┌───┘    │    │     └───┐ query
                   ▼        ▼    ▼         ▼
            ┌──────────┐ ┌────┐ ┌─────┐ ┌──────────┐
            │ watchdog │ │OCR │ │ASR  │ │ Ollama   │
            │ workers  │ │tess│ │whisp│ │ (local)  │
            └────┬─────┘ └─┬──┘ └─┬──┘ └────┬─────┘
                 │         │      │         │
                 ▼         ▼      ▼         ▼
            ┌──────────────────────────────────┐
            │  enrichment + chunking pipeline  │
            └──┬─────────────────────────┬─────┘
               ▼                         ▼
       ┌───────────────┐        ┌────────────────┐
       │  SQLite       │        │  Chroma        │
       │  (metadata,   │◄──────►│  (vectors +    │
       │   timeline,   │  ids   │   metadata)    │
       │   evidence)   │        │                │
       └───────────────┘        └────────────────┘
```

## Storage layers

Two stores answer different questions:

- **SQLite** — source of truth. Files, chunks (with FTS5 BM25 search), enrichments,
  timeline events, query log. Joinable with SQL.
- **Chroma** — embeddings + denormalized metadata for filtered semantic search.
  Chunks in Chroma reference SQLite chunk IDs; on a hit we always re-fetch the
  canonical text from SQLite.

## Request flows

### Ingestion (POST /ingest/file)

1. Multipart upload arrives. We sniff MIME via `python-magic`, normalize the filename,
   and persist to `EVG_UPLOAD_DIR`.
2. SHA-256 the bytes. If it matches an existing `files.sha256`, return `{duplicate: true}`.
3. Insert `files` row with `status=extracting`.
4. Dispatch to extractor (`pdf`, `image`, `audio`, `text`, …) → list of
   `ExtractedSegment` with positional metadata (page, char range, audio timestamp).
5. Chunk segments (semantic boundaries; ~512 tokens, 64 overlap).
6. Embed chunks (BGE-small by default).
7. Upsert into SQLite `chunks` (FTS triggers maintain `chunks_fts`) and into the
   Chroma collection (with metadata for filtering).
8. `status=indexed`. A background task runs LLM enrichment (summary / people /
   dates / tasks / category / sentiment) and emits `timeline_events`.

### Ask with proof (POST /query)

1. Sanitize the question (strip control chars, normalize whitespace).
2. **Hybrid retrieval**: top-32 from Chroma (cosine), top-32 from FTS5 (BM25),
   fused with **Reciprocal Rank Fusion (RRF)**.
3. Apply optional filters (`source_types`, `date_from`, `date_to`).
4. Drop chunks below `EVG_RETRIEVAL_MIN_SCORE`. Take top-K (default 8).
5. **If empty → return refusal immediately.** Never call the LLM.
6. Render the citation-mandatory prompt with the chunk IDs.
7. Call Ollama with `format=json` and `temperature=0`.
8. Parse JSON. **Validate every citation**:
   - `chunk_id` must be one we sent.
   - `excerpt` must be ≥12 chars and a verbatim substring (case/whitespace-insensitive)
     of the cited chunk's text.
9. If no valid citations survive validation → refusal.
10. Persist `query_log` row.

This validator is the load-bearing piece of the product. It is unit-tested in
`tests/unit/test_citation_validator.py`.

## Module map

```
backend/app/
  main.py              FastAPI factory, middleware, routers
  config.py            pydantic-settings (.env-driven)
  deps.py              SQLAlchemy engine, Chroma client, session helpers
  models/
    db.py              SQLAlchemy ORM
    schemas.py         pydantic request/response shapes
  routers/
    health, ingest, query, evidence, timeline, files, reindex
  services/
    ingestion          orchestrate extract → chunk → embed → store
    retrieval          hybrid Chroma + FTS5 + RRF
    answer             prompt rendering + JSON validation + citation contract
    enrichment         LLM-derived structured facts → enrichments + timeline
    timeline           query helpers
  security/
    paths              path traversal guard, safe filenames
    ratelimit          slowapi
    sanitize           text scrubbing
ai/
  chunking             recursive paragraph→sentence chunker
  embeddings           sentence-transformers wrapper
  llm                  async Ollama client (generate, generate_stream)
  prompts/             externalized prompt templates
ingestion/
  hashing              sha256 helpers
  metadata             mime sniff, EXIF, source_dt
  extractors/          pdf, image, audio, text, browser_export, clipboard
  watcher              watchdog → ingestion callback
db/
  schema.sql           canonical SQLite schema (applied on first boot)
```

## Key invariants

1. Every `Chunk` row has a corresponding vector in Chroma (or vice-versa). `/reindex`
   recovers from drift.
2. Every `Citation` returned to a user references a chunk that was actually retrieved
   for that question; its `excerpt` is a verbatim substring of that chunk.
3. No path read or write occurs unless the resolved path lies under one of
   `Settings.allowed_roots`.
4. The LLM is never called when retrieval is empty.
