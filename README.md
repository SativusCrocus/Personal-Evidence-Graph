# Personal Evidence Graph

> **Search Your Life. Prove Everything.**
>
> A local-first, proof-aware memory system. Capture and structure your digital
> evidence (PDFs, images, audio, text). Ask anything in plain English. Every
> answer cites the exact source — file, page, timestamp, excerpt — or refuses.
>
> No data ever leaves your machine.

---

## Why this exists

Generic chatbots make things up. RAG demos cite by file name and call it done.
This system enforces a stricter contract:

> **Every claim must be grounded in a verbatim excerpt of a real chunk that the
> retriever actually returned. If nothing matches, the answer is exactly
> `"No supporting evidence found."` — never a fabrication.**

That contract is the product. It's enforced in [`backend/app/services/answer.py`](backend/app/services/answer.py),
documented in [`docs/citation-contract.md`](docs/citation-contract.md), and
unit-tested in [`tests/unit/test_citation_validator.py`](tests/unit/test_citation_validator.py).

## Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js 15 + TypeScript + Tailwind + shadcn-style + Framer Motion + cmdk** | Fast, modern, dark-first, command-palette-driven |
| Backend  | **Python FastAPI** | Async, typed, batteries for SSE & background tasks |
| Vector store | **Chroma** (persistent) | Easy metadata filtering, zero-ops |
| Relational store | **SQLite + FTS5** | Single-file, BM25 for hybrid search |
| Embeddings | **sentence-transformers / `bge-small-en-v1.5`** | 384-dim, fast, accurate |
| LLM | **Ollama** (`llama3.1`, `mistral`, `gemma2:2b` for low-RAM) | Local, swappable |
| OCR | **Tesseract** (PaddleOCR fallback later) | Battle-tested |
| ASR | **whisper.cpp** (OpenAI whisper fallback) | Local transcription |
| Watcher | **watchdog** | Auto-ingest dropped folders |

## Install (macOS)

```bash
git clone <this repo>
cd personal-evidence-graph
./scripts/install_mac.sh
./scripts/pull_models.sh
./scripts/dev.sh
```

Open **http://localhost:3000**. The API is on **http://localhost:8000** with
docs at `/docs`.

### Linux

```bash
./scripts/install_linux.sh
./scripts/pull_models.sh
./scripts/dev.sh
```

### Windows (PowerShell, elevated)

```powershell
.\scripts\install_windows.ps1
ollama pull llama3.1:8b
.\.venv\Scripts\Activate.ps1
# in one terminal:
cd backend; uvicorn app.main:app --port 8000 --reload
# in another:
cd frontend; npm run dev
```

### Manual prerequisites (any platform)

Install these system tools on PATH:

- Python 3.11+
- Node 20+
- [Ollama](https://ollama.com)
- Tesseract OCR
- FFmpeg (for whisper)
- libmagic (`brew install libmagic` / `apt install libmagic1`)
- Optional: `whisper.cpp` (`main` binary on PATH) for fast transcription, or `pip install openai-whisper`

Then:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e backend
pip install -e "backend[dev]"
cd frontend && npm install && cd ..
cp .env.example .env   # review EVG_WATCHED_ROOTS!
```

## Usage

1. **Import** — open http://localhost:3000/import. Drag & drop files (PDFs,
   images, audio, text). Or set `EVG_WATCHED_ROOTS` and use the folder ingest box.
2. **Dashboard** — see counts, recent timeline, system health.
3. **Ask** — `⌘K` opens the command palette. Type a question and press Enter.
   The answer panel shows the response on the left and citations on the right.
4. **Click a citation** — opens `/evidence/{id}` with the chunk on the left and
   the original file rendered on the right (PDF.js / image / audio with
   timestamp jump).
5. **Timeline** — chronological reconstruction across every source, filterable
   by date and keyword.
6. **Settings** — model picker, storage stats, "Rebuild index".

## Configuration (.env)

See [`.env.example`](.env.example) for the full list with defaults. The most
important ones:

- `EVG_DATA_DIR` — where everything lives. Defaults to `./data`.
- `EVG_WATCHED_ROOTS` — comma-separated absolute paths the user has authorized
  for `/ingest/folder`. Anything outside these is rejected.
- `EVG_LLM_MODEL` — Ollama model tag. Default `llama3.1:8b`.
- `EVG_LLM_FALLBACK_MODEL` — used in low-RAM mode. Default `gemma2:2b`.
- `EVG_RETRIEVAL_MIN_SCORE` — semantic similarity floor. Below this, the system
  refuses rather than calls the LLM. Default `0.35`.

## Tests

```bash
source .venv/bin/activate
pytest tests
```

Notable suites:

- [`tests/integration/test_no_hallucination.py`](tests/integration/test_no_hallucination.py)
  — the core invariant. Empty DB → refusal. Unreachable LLM → refusal.
- [`tests/unit/test_citation_validator.py`](tests/unit/test_citation_validator.py)
  — exhaustive tests of `_validate()`.
- [`tests/unit/test_paths_security.py`](tests/unit/test_paths_security.py)
  — path-traversal guard.
- [`tests/unit/test_dedup.py`](tests/unit/test_dedup.py)
  — SHA-based deduplication end-to-end.
- [`tests/integration/test_ingest_text.py`](tests/integration/test_ingest_text.py)
  — text ingestion writes both SQLite and Chroma in lockstep.
- [`tests/integration/test_api_endpoints.py`](tests/integration/test_api_endpoints.py)
  — health, ingest, query, security headers.
- [`tests/integration/test_search_accuracy.py`](tests/integration/test_search_accuracy.py)
  — hybrid retrieval finds the known phrase.

Tests use a per-session temp dir (see [`tests/conftest.py`](tests/conftest.py))
so they never touch your real evidence DB.

## Verification (acceptance test for the MVP)

1. `./scripts/dev.sh` — backend on `:8000`, frontend on `:3000`.
2. `curl http://localhost:8000/health` returns `{"ok": true, "db": true, "chroma": true, "ollama": true}`.
3. Open `/import`, drop a sample PDF or text file. Within seconds it appears in
   the list with status `indexed` and a chunk count > 0.
4. On `/search`, ask a question whose answer is in the file. Response renders
   with ≥ 1 citation card. Click → `/evidence/[id]` opens with the highlight.
5. On `/search`, ask something completely unrelated. Response is exactly
   `"No supporting evidence found."` with zero citations. (Asserted by
   `test_no_hallucination.py`.)
6. Visit `/timeline` — events from your file appear sorted by date.
7. `pytest tests` — all green.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — system overview, request flows, module map.
- [`docs/citation-contract.md`](docs/citation-contract.md) — the no-hallucination invariant, formalized.
- [`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md) — extractors, chunking, persistence, idempotency.
- [`docs/security.md`](docs/security.md) — threat model, defenses, roadmap.
- [`docs/api.md`](docs/api.md) — every endpoint with example payloads.

## Folder layout

```
personal-evidence-graph/
├── frontend/      Next.js 15 app (pages, components, api client)
├── backend/       FastAPI app (routers, services, security, models)
├── ai/            chunking, embeddings, LLM client, prompt templates
├── ingestion/     extractors, hashing, metadata, watchdog
├── db/            schema.sql, migrations
├── scripts/       install_*.sh, pull_models.sh, dev.sh, reset_db.sh
├── tests/         unit + integration
├── docs/          architecture, citation contract, ingestion, security, api
├── docker/        optional postgres compose for v1.x
├── installers/    placeholder for Tauri (post-MVP)
├── .env.example
└── README.md
```

## Launch checklist

- [ ] System deps installed (`tesseract`, `ffmpeg`, `libmagic`, `ollama`).
- [ ] `scripts/install_<platform>.sh` succeeds on a fresh machine.
- [ ] `scripts/pull_models.sh` pulls the chosen Ollama model and warms embeddings.
- [ ] `scripts/dev.sh` starts both processes; `/health` is `ok: true` everywhere.
- [ ] At least one of each source type ingests cleanly (PDF, image, audio, text).
- [ ] A real question answers with valid citations.
- [ ] An unrelated question refuses with the exact refusal string.
- [ ] `pytest tests` passes.
- [ ] `EVG_WATCHED_ROOTS` is set to whatever folders you actually want auto-ingested.
- [ ] `.env` is **not** committed (covered by `.gitignore`).
- [ ] `data/` is **not** committed.

## What's NOT in the MVP (deferred to v1.1+)

Captured in the plan; tracked here so expectations are clear:

- Contradiction Engine (changed numbers, conflicting promises)
- Obligation Engine (deadlines, unpaid invoices, follow-ups)
- Tauri desktop packaging + signed installers
- Browser extension capture + screenshot hotkey
- Voice-memo instant ingest from menubar
- Invoice fraud detection
- Memory heatmap
- At-rest DB encryption (sqlcipher)
- Encrypted-sync team tier
- Multi-user roles, signed sessions, CSRF

These are well-defined enough to slot into a v1.1 plan once the MVP is validated
end-to-end.

## License

Proprietary. All rights reserved.
