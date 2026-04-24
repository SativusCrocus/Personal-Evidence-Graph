from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import Sequence

log = logging.getLogger("evg.embeddings")

_lock = threading.Lock()
_model = None
_model_name = ""


def _load(model_name: str):
    """Lazy-load sentence-transformers model. Cached by name."""
    global _model, _model_name
    with _lock:
        if _model is not None and _model_name == model_name:
            return _model
        from sentence_transformers import SentenceTransformer  # heavy import

        log.info("loading embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
        _model_name = model_name
        return _model


def embed(texts: Sequence[str], model_name: str) -> list[list[float]]:
    if not texts:
        return []
    model = _load(model_name)
    vecs = model.encode(
        list(texts),
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=32,
    )
    return [v.tolist() for v in vecs]


def embed_one(text: str, model_name: str) -> list[float]:
    return embed([text], model_name)[0]


@lru_cache
def embedding_dim(model_name: str) -> int:
    model = _load(model_name)
    return int(model.get_sentence_embedding_dimension())
