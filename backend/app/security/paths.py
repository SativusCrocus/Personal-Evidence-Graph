from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable


class PathSafetyError(ValueError):
    """Raised when a user-supplied path escapes its allowlisted root."""


_FILENAME_BAD = re.compile(r"[\x00-\x1f/\\:*?\"<>|]")


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_inside(roots: Iterable[Path], user_path: str | os.PathLike[str]) -> Path:
    """Resolve `user_path` and assert it lies under at least one allowlisted root.

    Defends against:
      - relative `..` escapes
      - absolute paths outside the allowlist
      - symlinks pointing outside (resolve() follows them)
    """
    if user_path is None or str(user_path).strip() == "":
        raise PathSafetyError("empty path")
    candidate = Path(user_path).expanduser().resolve()
    for r in roots:
        rr = r.expanduser().resolve()
        try:
            candidate.relative_to(rr)
            return candidate
        except ValueError:
            continue
    raise PathSafetyError(f"path outside allowed roots: {candidate}")


def safe_filename(name: str, max_len: int = 200) -> str:
    """Normalize a filename for on-disk storage."""
    if not name:
        return "untitled"
    name = unicodedata.normalize("NFKD", name)
    name = _FILENAME_BAD.sub("_", name).strip(". ")
    if not name:
        name = "untitled"
    if len(name) > max_len:
        stem, _, ext = name.rpartition(".")
        if stem and ext and len(ext) <= 8:
            stem = stem[: max_len - len(ext) - 1]
            name = f"{stem}.{ext}"
        else:
            name = name[:max_len]
    return name
