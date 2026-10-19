from __future__ import annotations

from loguru import logger
from fastapi import FastAPI

from app.core.bootstrap import init as bootstrap_init
from app.core.lifespan import lifespan
from app.api.torznab import router as torznab_router
from app.api.qbittorrent import router as qbittorrent_router
from app.api.health import router as health_router
from app.api.legacy_downloader import router as legacy_router
from app.api.strm import router as strm_router
from app.cli import run_server
from app.cors import apply_cors_middleware
from app.config import (
    ANIBRIDGE_CORS_ALLOW_CREDENTIALS,
    ANIBRIDGE_CORS_ORIGINS,
    CATALOG_CONFIG,
)
from app.utils.logger import config as configure_logger

configure_logger()

bootstrap_init()


app = FastAPI(title="AniBridge-Minimal", lifespan=lifespan)
if ANIBRIDGE_CORS_ORIGINS:
    apply_cors_middleware(
        app,
        origins=ANIBRIDGE_CORS_ORIGINS,
        allow_credentials=ANIBRIDGE_CORS_ALLOW_CREDENTIALS,
    )
if CATALOG_CONFIG.mode == "query":
    import logging

    logging.getLogger("uvicorn.access").disabled = True
    from app.catalog.http import router as query_router
    from app.catalog.qbit_http import router as query_qbit_router
    from app.catalog.strm_http import router as query_strm_router
    from app.catalog.management import router as management_router
    from app.catalog.management_auth import ManagementAuth
    from app.config import MANAGEMENT_API_TOKEN

    app.state.management_auth = ManagementAuth(
        MANAGEMENT_API_TOKEN, tuple(ANIBRIDGE_CORS_ORIGINS)
    )
    app.include_router(management_router)
    app.include_router(query_router)
    app.include_router(query_qbit_router)
    app.include_router(query_strm_router)
else:
    app.include_router(torznab_router)
app.include_router(qbittorrent_router)
app.include_router(health_router)
app.include_router(legacy_router)
app.include_router(strm_router)


if __name__ == "__main__":
    logger.info("Starting AniBridge FastAPI server...")
    run_server(app)
