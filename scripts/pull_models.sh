#!/usr/bin/env bash
# Pull required Ollama models and warm the embedding model cache.
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

if ! command -v ollama >/dev/null 2>&1; then
  echo "[pull_models] ollama not on PATH. Install it first." >&2
  exit 1
fi

# Ensure the daemon is up (no-op if already running)
ollama list >/dev/null 2>&1 || (ollama serve >/tmp/ollama.log 2>&1 &) && sleep 2

# shellcheck disable=SC1091
LLM_MODEL="${EVG_LLM_MODEL:-llama3.1:8b}"
FALLBACK="${EVG_LLM_FALLBACK_MODEL:-gemma2:2b}"

echo "[pull_models] pulling $LLM_MODEL …"
ollama pull "$LLM_MODEL"

echo "[pull_models] pulling $FALLBACK (low-RAM fallback) …"
ollama pull "$FALLBACK" || true

# Warm sentence-transformers embed model (download to local cache)
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
EMBED="${EVG_EMBED_MODEL:-BAAI/bge-small-en-v1.5}"
python - <<PY
from sentence_transformers import SentenceTransformer
print("[pull_models] downloading", "$EMBED")
SentenceTransformer("$EMBED")
print("[pull_models] embed model ready.")
PY

echo "[pull_models] done."
