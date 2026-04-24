from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_prefix="EVG_",
        case_sensitive=False,
        extra="ignore",
    )

    data_dir: Path = Field(default=Path("./data"))
    upload_dir: Path = Field(default=Path("./data/uploads"))
    chroma_dir: Path = Field(default=Path("./data/chroma"))
    sqlite_path: Path = Field(default=Path("./data/evidence.db"))
    watched_roots: str = Field(default="")

    ollama_host: str = Field(default="http://localhost:11434")
    llm_model: str = Field(default="llama3.1:8b")
    llm_fallback_model: str = Field(default="gemma2:2b")
    embed_model: str = Field(default="BAAI/bge-small-en-v1.5")
    whisper_bin: str = Field(default="whisper")
    whisper_model: str = Field(default="base.en")
    tesseract_bin: str = Field(default="tesseract")

    cors_origins: str = Field(default="http://localhost:3000")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)

    max_upload_mb: int = Field(default=100, ge=1, le=10_000)
    rate_limit_query: str = Field(default="30/minute")
    rate_limit_ingest: str = Field(default="60/minute")
    retrieval_k: int = Field(default=8, ge=1, le=64)
    retrieval_min_score: float = Field(default=0.35, ge=0.0, le=1.0)

    chunk_tokens: int = Field(default=512, ge=64, le=4096)
    chunk_overlap: int = Field(default=64, ge=0, le=512)
    low_ram_mode: bool = Field(default=False)

    log_level: str = Field(default="INFO")

    @field_validator("data_dir", "upload_dir", "chroma_dir", "sqlite_path", mode="after")
    @classmethod
    def _resolve(cls, v: Path) -> Path:
        return v.expanduser().resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def watched_root_list(self) -> list[Path]:
        out: list[Path] = []
        for raw in self.watched_roots.split(","):
            raw = raw.strip()
            if not raw:
                continue
            p = Path(raw).expanduser().resolve()
            if p.exists() and p.is_dir():
                out.append(p)
        return out

    @property
    def allowed_roots(self) -> list[Path]:
        roots = [self.data_dir, self.upload_dir, *self.watched_root_list]
        seen: set[Path] = set()
        out: list[Path] = []
        for r in roots:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.upload_dir, self.chroma_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
