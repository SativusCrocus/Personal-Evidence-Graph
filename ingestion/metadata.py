from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("evg.metadata")


def file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def detect_mime(path: Path) -> str:
    """Magic-byte sniff. Falls back to extension when libmagic unavailable."""
    try:
        import magic  # python-magic

        return magic.from_file(str(path), mime=True) or "application/octet-stream"
    except Exception as e:  # noqa: BLE001
        log.debug("python-magic unavailable: %s; falling back to extension", e)
        ext = path.suffix.lower()
        return _EXT_TO_MIME.get(ext, "application/octet-stream")


def source_type_from_mime(mime: str, path: Path) -> str:
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("text/") or mime in {
        "application/json", "application/xml", "application/yaml",
    }:
        return "text"
    if path.suffix.lower() in {".html", ".htm", ".mhtml"}:
        return "browser"
    return "other"


def exif_datetime(path: Path) -> Optional[datetime]:
    try:
        import exifread  # type: ignore[import-untyped]
    except Exception:  # noqa: BLE001
        return None
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False, stop_tag="EXIF DateTimeOriginal")
        for key in ("EXIF DateTimeOriginal", "Image DateTime", "EXIF DateTimeDigitized"):
            if key in tags:
                raw = str(tags[key])
                return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception as e:  # noqa: BLE001
        log.debug("exif read failed for %s: %s", path, e)
    return None


def best_source_dt(path: Path, mime: str) -> Optional[datetime]:
    if mime.startswith("image/"):
        dt = exif_datetime(path)
        if dt:
            return dt
    try:
        return file_mtime(path)
    except OSError:
        return None


def file_size(path: Path) -> int:
    return os.path.getsize(path)


_EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".heic": "image/heic",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".rtf": "application/rtf",
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".csv": "text/csv",
}
