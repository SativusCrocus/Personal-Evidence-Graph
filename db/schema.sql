-- Personal Evidence Graph — canonical SQLite schema.
-- Applied at startup if tables do not exist; alembic owns migrations beyond v1.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous  = NORMAL;

CREATE TABLE IF NOT EXISTS files (
  id            TEXT PRIMARY KEY,
  path          TEXT NOT NULL UNIQUE,
  display_name  TEXT NOT NULL,
  sha256        TEXT NOT NULL UNIQUE,
  mime          TEXT NOT NULL,
  bytes         INTEGER NOT NULL,
  source_type   TEXT NOT NULL CHECK (source_type IN
                  ('pdf','image','audio','text','browser','clipboard','video','other')),
  ingested_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  source_dt     TIMESTAMP,
  status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','extracting','enriching','indexed','failed')),
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_source_dt ON files(source_dt);
CREATE INDEX IF NOT EXISTS idx_files_status    ON files(status);
CREATE INDEX IF NOT EXISTS idx_files_type      ON files(source_type);

CREATE TABLE IF NOT EXISTS chunks (
  id            TEXT PRIMARY KEY,
  file_id       TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  ord           INTEGER NOT NULL,
  text          TEXT NOT NULL,
  char_start    INTEGER,
  char_end      INTEGER,
  page          INTEGER,
  ts_start_ms   INTEGER,
  ts_end_ms     INTEGER,
  tokens        INTEGER,
  UNIQUE (file_id, ord)
);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text,
  content='chunks',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
  INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
END;

CREATE TABLE IF NOT EXISTS enrichments (
  id            TEXT PRIMARY KEY,
  chunk_id      TEXT REFERENCES chunks(id) ON DELETE CASCADE,
  file_id       TEXT REFERENCES files(id)  ON DELETE CASCADE,
  kind          TEXT NOT NULL CHECK (kind IN
                  ('summary','person','date','task','category','sentiment','risk','commitment')),
  value         TEXT NOT NULL,
  confidence    REAL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_enrich_kind  ON enrichments(kind);
CREATE INDEX IF NOT EXISTS idx_enrich_file  ON enrichments(file_id);
CREATE INDEX IF NOT EXISTS idx_enrich_chunk ON enrichments(chunk_id);

CREATE TABLE IF NOT EXISTS timeline_events (
  id            TEXT PRIMARY KEY,
  occurred_at   TIMESTAMP NOT NULL,
  file_id       TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  chunk_id      TEXT REFERENCES chunks(id)        ON DELETE CASCADE,
  title         TEXT NOT NULL,
  description   TEXT,
  kind          TEXT,
  confidence    REAL
);
CREATE INDEX IF NOT EXISTS idx_timeline_dt   ON timeline_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_timeline_kind ON timeline_events(kind);

CREATE TABLE IF NOT EXISTS query_log (
  id              TEXT PRIMARY KEY,
  asked_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  question        TEXT NOT NULL,
  answer          TEXT,
  cited_chunk_ids TEXT,
  refused         INTEGER NOT NULL DEFAULT 0,
  latency_ms      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_query_log_dt ON query_log(asked_at);

CREATE TABLE IF NOT EXISTS schema_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', '1');
