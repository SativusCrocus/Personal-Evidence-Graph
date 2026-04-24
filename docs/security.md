# Security model

Personal Evidence Graph is **local-first by design**. The backend binds to
`127.0.0.1` and refuses cross-origin traffic outside `EVG_CORS_ORIGINS`
(default: `http://localhost:3000`). Nothing leaves the machine.

## Threat model (v1)

We protect against:

- Malformed uploads triggering crashes or path-traversal writes.
- Malicious filenames overwriting unrelated files.
- A bystander on the same machine using the unauthenticated API to read your data
  (mitigated only by OS-level file-system permissions; see "What v1 does not protect").
- An LLM response inventing chunk IDs or citing fabricated excerpts.
- A user-supplied folder path tricking `/ingest/folder` into walking `/etc`.

We do **not** protect against:

- A multi-user machine where another OS user has read access to `EVG_DATA_DIR`.
- Disk-level theft (the SQLite file is unencrypted in v1; sqlcipher in v1.1).
- An attacker who can already run code as your user.

## Defenses

| Concern | Defense | Code |
|---|---|---|
| Path traversal (`..`, absolute escapes, symlinks) | `Path.resolve()` + allowlisted root check | [`backend/app/security/paths.py`](../backend/app/security/paths.py) |
| Filename injection (slashes, control chars) | `safe_filename()` normalizes before write | same |
| Upload bombs | `EVG_MAX_UPLOAD_MB` cap + reject empty | [`backend/app/routers/ingest.py`](../backend/app/routers/ingest.py) |
| Wrong content-type | Magic-byte sniff via `python-magic`, never trust client | [`ingestion/metadata.py`](../ingestion/metadata.py) |
| Cross-origin abuse | `CORSMiddleware` allowlist (no `*`) | [`backend/app/main.py`](../backend/app/main.py) |
| Rate abuse | `slowapi` per-IP limits on `/query`, `/ingest/*` | [`backend/app/security/ratelimit.py`](../backend/app/security/ratelimit.py) |
| SQL injection | SQLAlchemy parameterized queries; FTS5 query has special chars stripped | [`backend/app/services/retrieval.py`](../backend/app/services/retrieval.py) |
| XSS | React auto-escapes; raw file previews rendered in `sandbox="allow-same-origin"` iframe | [`frontend/components/evidence-preview.tsx`](../frontend/components/evidence-preview.tsx) |
| Subprocess injection (whisper, tesseract) | `shell=False`, validated arg list | [`ingestion/extractors/audio.py`](../ingestion/extractors/audio.py) |
| Hallucinated citations | Validator drops citations whose IDs / excerpts don't match retrieved chunks | [`backend/app/services/answer.py`](../backend/app/services/answer.py) |
| Header tampering | `X-Content-Type-Options`, `X-Frame-Options: DENY`, restrictive `Permissions-Policy` | `backend/app/main.py`, `frontend/next.config.mjs` |

## Operational hygiene

- Secrets only in `.env` (never committed; covered by `.gitignore`).
- `EVG_WATCHED_ROOTS` is **opt-in**; folder ingestion outside an allowlisted root is
  rejected at the router level.
- The "Wipe all data" affordance (Settings page → `scripts/reset_db.sh`) is
  irreversible and prompts twice.

## Roadmap

- **v1.1** — at-rest encryption via sqlcipher; passphrase-on-launch mode.
- **v1.2** — signed sessions, CSRF tokens, role-based access (when/if a remote
  frontend or team-tier ships).
- **v1.x** — automated dependency vulnerability scanning in CI.
