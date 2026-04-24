from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

CHUNK = 1 << 20


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_stream(stream: BinaryIO) -> str:
    h = hashlib.sha256()
    while True:
        block = stream.read(CHUNK)
        if not block:
            break
        h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
