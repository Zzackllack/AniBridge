from __future__ import annotations

from loguru import logger
from fastapi import FastAPI

from app.core.bootstrap import init as bootstrap_init
from app.core.lifespan import lifespan
from app.api.torznab import router as torznab_router
from app.api.qbittorrent import router as qbittorrent_router
from app.api.health import router as health_router
from app.api.legacy_downloader import router as legacy_router
from app.cli import run_server

bootstrap_init()


app = FastAPI(title="AniBridge-Minimal", lifespan=lifespan)
app.include_router(torznab_router)
app.include_router(qbittorrent_router)
app.include_router(health_router)
app.include_router(legacy_router)


if __name__ == "__main__":
    logger.info("Starting AniBridge FastAPI server...")
    run_server(app)
