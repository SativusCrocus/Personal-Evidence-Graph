#!/usr/bin/env bash
# One-command run: launches Ollama (if needed), backend, and frontend.
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

PIDS=()
cleanup() {
  echo
  echo "[dev] shutting down ($([[ ${#PIDS[@]} -gt 0 ]] && echo "${PIDS[*]}" || echo none))…"
  for p in "${PIDS[@]:-}"; do
    kill "$p" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

if command -v ollama >/dev/null 2>&1; then
  if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "[dev] starting ollama daemon…"
    ollama serve >/tmp/ollama.log 2>&1 &
    PIDS+=($!)
    sleep 2
  fi
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[dev] wrote default .env"
fi

if [[ ! -d .venv ]]; then
  echo "[dev] no .venv found. Run scripts/install_mac.sh (or your platform script) first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[dev] starting backend on :8000…"
(
  cd backend
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
) &
PIDS+=($!)

echo "[dev] starting frontend on :3000…"
(
  cd frontend
  npm run dev
) &
PIDS+=($!)

echo
echo "[dev] open http://localhost:3000   (api docs: http://localhost:8000/docs)"
echo "[dev] ctrl-c to stop."
wait
