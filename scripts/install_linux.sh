#!/usr/bin/env bash
# Install system dependencies on Debian/Ubuntu, then bootstrap Python + Node.
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    nodejs npm \
    tesseract-ocr ffmpeg \
    libmagic1 poppler-utils \
    build-essential
else
  echo "[install_linux] non-Debian distro: install python3.11, node, tesseract, ffmpeg, libmagic, poppler manually." >&2
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "[install_linux] installing Ollama…"
  curl -fsSL https://ollama.com/install.sh | sh
fi

PYTHON="$(command -v python3.11 || command -v python3)"
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel
pip install -e backend
pip install -e "backend[dev]"

cd frontend && npm install && cd ..

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "[install_linux] done."
