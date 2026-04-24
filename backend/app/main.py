from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

# Make sibling package roots importable
_HERE = Path(__file__).resolve()
_PROJ = _HERE.parents[2]
if str(_PROJ) not in sys.path:
    sys.path.insert(0, str(_PROJ))

from . import __version__
from .config import get_settings
from .deps import get_chroma, get_engine
from .routers import evidence, files, health, ingest, query, reindex, timeline
from .security import limiter

log = logging.getLogger("evg")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    _configure_logging(s.log_level)
    s.ensure_dirs()
    get_engine()
    get_chroma()
    log.info("evidence-graph backend ready (v%s, port %d)", __version__, s.port)
    yield
    log.info("evidence-graph backend shutting down")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Personal Evidence Graph",
        version=__version__,
        description="Local-first proof-aware memory system. Search Your Life. Prove Everything.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(_: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": f"rate limit exceeded: {exc.detail}"},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "Authorization"],
        max_age=600,
    )

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(query.router)
    app.include_router(timeline.router)
    app.include_router(evidence.router)
    app.include_router(reindex.router)
    app.include_router(files.router)

    @app.get("/")
    def _root():
        return {
            "name": "personal-evidence-graph",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
