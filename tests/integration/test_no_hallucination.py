"""The most important test in the system.

If retrieval returns nothing relevant, the answer service MUST refuse with
exactly "No supporting evidence found." and zero citations. This test runs
without an Ollama backend (the LLM path is not invoked when retrieval is empty).
"""
from __future__ import annotations

import asyncio

from app.services.answer import REFUSAL, answer_with_proof


def test_refuses_when_retrieval_empty():
    """No files indexed → empty retrieval → guaranteed refusal."""
    res = asyncio.run(answer_with_proof("Did the client approve the pricing?"))
    assert res.refused is True
    assert res.answer == REFUSAL
    assert res.citations == []
    assert res.confidence == 0.0


def test_refuses_when_llm_unreachable(sample_text_file):
    """Even with retrieval populated, an unreachable LLM must refuse — not hallucinate."""
    from app.services import ingestion

    ingestion.ingest_path(sample_text_file)
    res = asyncio.run(answer_with_proof("What was the approved price?"))
    assert res.refused is True
    assert res.answer == REFUSAL
    assert res.citations == []
