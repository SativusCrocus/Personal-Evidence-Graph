from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ai.llm import OllamaClient  # noqa: E402

from .. import __version__
from ..config import Settings
from ..deps import get_collection, get_engine, settings_dep
from ..models.schemas import HealthStatus

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthStatus)
async def health(s: Settings = Depends(settings_dep)) -> HealthStatus:
    db_ok = False
    try:
        with get_engine().connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        db_ok = True
    except Exception:  # noqa: BLE001
        pass

    chroma_ok = False
    try:
        get_collection().count()
        chroma_ok = True
    except Exception:  # noqa: BLE001
        pass

    ollama_ok = False
    client = OllamaClient(s.ollama_host, s.llm_model, s.llm_fallback_model)
    try:
        ollama_ok = await client.is_alive()
    finally:
        await client.aclose()

    return HealthStatus(
        ok=db_ok and chroma_ok,
        version=__version__,
        db=db_ok,
        chroma=chroma_ok,
        ollama=ollama_ok,
        embed_model=s.embed_model,
        llm_model=s.llm_model,
    )
