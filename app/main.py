"""
main.py
-------
FastAPI application factory.
Handles app startup (data loading) via lifespan context manager.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import APP_TITLE, APP_DESCRIPTION, APP_VERSION
from app.routers import boundary
from app.services.data_loader import geo_store

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: load heavy data once at startup, release on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Starting up: loading geo data …")
    geo_store.load()
    logger.info("=== Startup complete. API is ready.")
    yield
    logger.info("=== Shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS – allow all origins for development; tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(boundary.router)

    @app.get("/", tags=["Health"])
    async def root():
        return {
            "service": APP_TITLE,
            "version": APP_VERSION,
            "status": "ok",
            "docs": "/docs",
        }

    @app.get("/health", tags=["Health"])
    async def health():
        return {
            "status": "ok",
            "data_loaded": geo_store.is_loaded,
        }

    return app


app = create_app()
