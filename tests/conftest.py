from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True, scope="session")
def _isolate_storage():
    """Point all data paths at a per-session temp dir so tests never touch the real DB."""
    tmp = Path(tempfile.mkdtemp(prefix="evg_test_"))
    os.environ["EVG_DATA_DIR"] = str(tmp / "data")
    os.environ["EVG_UPLOAD_DIR"] = str(tmp / "data" / "uploads")
    os.environ["EVG_CHROMA_DIR"] = str(tmp / "data" / "chroma")
    os.environ["EVG_SQLITE_PATH"] = str(tmp / "data" / "evidence.db")
    os.environ["EVG_WATCHED_ROOTS"] = str(tmp / "data")
    os.environ["EVG_OLLAMA_HOST"] = "http://127.0.0.1:65535"
    os.environ.setdefault("EVG_LOG_LEVEL", "WARNING")

    from app.config import get_settings  # noqa: E402

    get_settings.cache_clear()
    s = get_settings()
    s.ensure_dirs()
    yield s


@pytest.fixture
def fixtures_dir() -> Path:
    p = PROJECT_ROOT / "tests" / "fixtures"
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
def sample_text_file(fixtures_dir: Path) -> Path:
    p = fixtures_dir / "sample.txt"
    p.write_text(
        "On Jan 4 2025, the client approved the pricing of $4,800 for Phase 1.\n\n"
        "Delivery is due by Friday Jan 17 2025. Acme Corp will pay net 30.\n\n"
        "We agreed the scope cannot change without written consent."
    )
    return p
