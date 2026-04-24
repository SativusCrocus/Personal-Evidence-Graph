# Installers

Native desktop packaging (Tauri) is **deferred to v1.1**. For the MVP, run as a
local web app via `scripts/dev.sh`. The post-MVP plan:

1. `tauri init` rooted at `frontend/`, target `dist/` of `next build && next export`.
2. Bundle the FastAPI backend either as:
   - a sidecar binary built with `pyinstaller` (cross-platform, larger artifact), or
   - launched via the user's system Python (smaller artifact, more setup friction).
3. Code-sign + notarize for macOS; sign with Authenticode for Windows; AppImage on Linux.
4. Auto-update channel via Tauri's built-in updater.

This directory will hold the platform-specific build configs once that work begins.
