from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger("evg.llm")
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class LLMError(RuntimeError):
    pass


def load_prompt(name: str) -> str:
    p = PROMPTS_DIR / f"{name}.txt"
    return p.read_text(encoding="utf-8")


class OllamaClient:
    """Thin async client over Ollama's HTTP API.

    Methods:
      - generate(): JSON / structured one-shot
      - generate_stream(): token streaming (SSE-friendly)
      - is_alive(): readiness probe
    """

    def __init__(self, host: str, model: str, fallback_model: Optional[str] = None) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.fallback_model = fallback_model
        self._client = httpx.AsyncClient(base_url=self.host, timeout=120.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def is_alive(self) -> bool:
        try:
            r = await self._client.get("/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def models_available(self) -> list[str]:
        try:
            r = await self._client.get("/api/tags", timeout=5.0)
            r.raise_for_status()
            return [m.get("name", "") for m in (r.json().get("models") or [])]
        except Exception as e:  # noqa: BLE001
            log.debug("ollama tags failed: %s", e)
            return []

    async def generate(
        self,
        prompt: str,
        *,
        format_json: bool = False,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        body = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            body["format"] = "json"

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        ):
            with attempt:
                r = await self._client.post("/api/generate", json=body)
                if r.status_code == 404 and self.fallback_model and not model:
                    log.warning("model %s not found; trying fallback %s",
                                self.model, self.fallback_model)
                    body["model"] = self.fallback_model
                    r = await self._client.post("/api/generate", json=body)
                r.raise_for_status()
                data = r.json()
                return data.get("response", "")
        raise LLMError("unreachable")

    async def generate_stream(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        body = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        async with self._client.stream("POST", "/api/generate", json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tok = chunk.get("response")
                if tok:
                    yield tok
                if chunk.get("done"):
                    return
