from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .models.db import Base

log = logging.getLogger("evg.deps")

CHROMA_COLLECTION = "evg_chunks"


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):  # type: ignore[no-untyped-def]
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA synchronous = NORMAL")
    cur.close()


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    s.ensure_dirs()
    url = f"sqlite:///{s.sqlite_path}"
    eng = create_engine(url, future=True, echo=False, pool_pre_ping=True)
    _bootstrap_schema(eng)
    return eng


def _bootstrap_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    schema_sql = (Path(__file__).resolve().parent.parent.parent / "db" / "schema.sql")
    if schema_sql.exists():
        with engine.begin() as conn:
            for stmt in _split_sql(schema_sql.read_text()):
                if stmt.strip():
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:  # noqa: BLE001
                        log.debug("schema stmt skipped: %s", e)


def _split_sql(sql: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    in_trigger = False
    for line in sql.splitlines():
        stripped = line.strip().upper()
        if stripped.startswith("CREATE TRIGGER"):
            in_trigger = True
        buf.append(line)
        if in_trigger:
            if stripped.endswith("END;"):
                out.append("\n".join(buf))
                buf = []
                in_trigger = False
        elif line.rstrip().endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    Session_ = _session_factory()
    s = Session_()
    try:
        yield s
    finally:
        s.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    Session_ = _session_factory()
    s = Session_()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@lru_cache
def get_chroma() -> chromadb.api.ClientAPI:
    s = get_settings()
    s.ensure_dirs()
    client = chromadb.PersistentClient(
        path=str(s.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )
    client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    return client


def get_collection():
    return get_chroma().get_or_create_collection(
        CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def settings_dep() -> Settings:
    return get_settings()
