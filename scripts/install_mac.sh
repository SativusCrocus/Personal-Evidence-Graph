#!/usr/bin/env bash
# Install system dependencies on macOS via Homebrew, then bootstrap Python + Node.
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

if ! command -v brew >/dev/null 2>&1; then
  echo "[install_mac] Homebrew not found. Install from https://brew.sh first." >&2
  exit 1
fi

echo "[install_mac] installing system packages…"
brew update
brew install python@3.11 node@20 tesseract ffmpeg pkg-config libmagic poppler

if ! command -v ollama >/dev/null 2>&1; then
  echo "[install_mac] installing Ollama…"
  brew install --cask ollama
fi

echo "[install_mac] creating Python virtualenv…"
PYTHON="$(command -v python3.11 || command -v python3)"
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel
pip install -e backend
pip install -e "backend[dev]"

echo "[install_mac] installing frontend deps…"
cd frontend && npm install && cd ..

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[install_mac] wrote .env (review EVG_WATCHED_ROOTS before ingesting)."
fi

echo "[install_mac] done. Next: scripts/pull_models.sh, then scripts/dev.sh"
