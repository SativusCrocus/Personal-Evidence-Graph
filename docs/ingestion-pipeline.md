# Ingestion Pipeline

## Stages

```
upload  →  store  →  hash/dedup  →  detect_mime  →  source_type  →  extract  →  chunk  →  embed  →  persist  →  enrich (bg)
```

| Stage | Responsibility | Code |
|---|---|---|
| **store** | Persist bytes under `EVG_UPLOAD_DIR` with a sanitized name | `services/ingestion.py::store_upload` |
| **hash/dedup** | SHA-256; if `files.sha256` exists, return the existing `file_id` and bail | `ingestion/hashing.py`, `services/ingestion.py::find_duplicate` |
| **detect_mime** | `python-magic` byte sniff (extension fallback if libmagic missing) | `ingestion/metadata.py::detect_mime` |
| **source_type** | Maps MIME to one of `pdf|image|audio|video|text|browser|clipboard|other` | `ingestion/metadata.py::source_type_from_mime` |
| **extract** | Dispatches to the right extractor by source_type, returns `ExtractedSegment[]` with positional metadata | `ingestion/extractors/*.py` |
| **chunk** | Recursive paragraph→sentence chunker; preserves page / timestamp metadata | `ai/chunking.py` |
| **embed** | sentence-transformers, cosine-normalized | `ai/embeddings.py` |
| **persist** | Insert `chunks` rows (FTS triggers populate `chunks_fts`); upsert vectors into Chroma | `services/ingestion.py::_persist_chunks_and_index` |
| **enrich** | Background LLM pass: summary, people, dates, tasks, category, sentiment → `enrichments` + `timeline_events` | `services/enrichment.py` |

## Extractor details

| Type | Extractor | Notes |
|---|---|---|
| `pdf` | `extractors/pdf.py` | `pypdfium2` per page; OCR fallback via `pytesseract` if a page has <30 chars of text |
| `image` | `extractors/image.py` | Tesseract OCR; honors EXIF `DateTimeOriginal` for `source_dt` |
| `audio` | `extractors/audio.py` | Tries `whisper.cpp` (`main` binary, JSON output) first; falls back to OpenAI's `whisper` CLI; preserves segment timestamps |
| `text` | `extractors/text.py` | UTF-8 with `latin-1` fallback; HTML is stripped (script/style removed) |
| `clipboard` | `extractors/clipboard.py` | Treats raw text as a single segment |
| `browser` | `extractors/browser_export.py` | Defers to text extractor |
| `video` | `extractors/audio.py` | Same path as audio (whisper transcribes the audio track) |

## Background enrichment

After ingestion succeeds, the router schedules `enrich_file(file_id)` as a
`BackgroundTask`. For the first 8 chunks of a file we render
`ai/prompts/enrich_metadata.txt` and ask the LLM (`format=json`). The result
becomes:

- `enrichments` rows (`summary`, `person`, `date`, `task`, `category`, `sentiment`)
- `timeline_events` rows for each parsed `date`, plus a fallback event using the
  file's `source_dt` if no in-text dates were found

Failures are tolerated silently — enrichment is "best-effort polish," never
required for retrieval to work.

## Idempotency

- Re-ingesting the same file returns `duplicate=true` and the original `file_id`.
- Re-running ingestion after a partial failure: `status` resets via `_mark_status`;
  rerun is safe.
- `POST /reindex` rebuilds Chroma from SQLite, so vector drift is recoverable.

## Failure modes & where they surface

| Failure | Where | What the user sees |
|---|---|---|
| Path traversal attempt | `services/ingestion.py::ingest_path` → `resolve_inside` | HTTP 400 |
| Upload too big | `routers/ingest.py` | HTTP 413 |
| Extractor returned no text | `services/ingestion.py` | File row with `status=indexed`, 0 chunks |
| Extraction crashed | `services/ingestion.py` | File row with `status=failed`, `error=...` |
| Embeddings model missing | `ai/embeddings.py` on first call | Backend log; HTTP 500 on the request that triggered it |
