"""FastAPI application factory and entrypoint.

Run in dev with:
    uv run uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.api import health
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.ratelimit import limiter

log = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    log.info("startup", environment=settings.environment, version=__version__)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PersonaAI API",
        version=__version__,
        description="Persistent, evidence-backed AI persona platform.",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Routers. More are mounted as milestones land.
    app.include_router(health.router)

    return app


def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limited", "message": "Too many requests", "details": {}}},
    )


app = create_app()
