"""FastAPI application factory and entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes import maps, matches, system
from .config import settings
from .database import init_db
from .logging_config import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    settings.ensure_dirs()
    init_db()
    logger.info(
        "%s v%s started (env=%s, detector=%s, ocr=%s)",
        settings.app_name, __version__, settings.environment,
        settings.detector_backend, settings.ocr_backend,
    )
    yield
    logger.info("Shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="Post-match Valorant coaching from on-screen vision only.",
        description=(
            "Analyzes recorded Valorant gameplay using computer vision. It reads "
            "only what was visible on the player's screen (viewport, minimap, "
            "killfeed, scoreboard, timer) and never game memory, packets, or "
            "hidden state."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_prefix = "/api"
    app.include_router(system.router, prefix=api_prefix)
    app.include_router(maps.router, prefix=api_prefix)
    app.include_router(matches.router, prefix=api_prefix)
    app.include_router(matches.rounds_router, prefix=api_prefix)

    @app.get("/", tags=["system"])
    def root() -> dict:
        return {"app": settings.app_name, "version": __version__, "docs": "/docs"}

    return app


app = create_app()
