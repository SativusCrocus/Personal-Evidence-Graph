#!/usr/bin/env bash
# DESTRUCTIVE: wipe local SQLite + Chroma + uploads. Asks for confirmation.
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJ_ROOT"

DATA_DIR="${EVG_DATA_DIR:-./data}"

echo "[reset_db] About to delete: $DATA_DIR"
read -r -p "Type YES to confirm: " ans
if [[ "$ans" != "YES" ]]; then
  echo "[reset_db] aborted."
  exit 1
fi

rm -rf "$DATA_DIR"
echo "[reset_db] wiped. Next run will recreate the schema."
