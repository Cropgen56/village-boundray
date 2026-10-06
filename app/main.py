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
    try:
        geo_store.load()
    except Exception:
        # Abort startup — never serve requests without boundary data
        logger.exception("=== Startup failed: could not load boundary data.")
        raise
    logger.info("=== Startup complete. API is ready.")
    yield
    logger.info("=== Shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    # Only the /boundary route is exposed, plus Swagger UI at /docs
    app = FastAPI(
        title="Maharashtra Boundary API",
        description=(
            "Given a coordinate (lat/lng) in Maharashtra, returns the boundary "
            "at village, taluka (sub-district), or district level."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    # CORS – allow all origins for development; tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(boundary.router)

    return app


app = create_app()
