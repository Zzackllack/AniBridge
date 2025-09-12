from __future__ import annotations

from fastapi import APIRouter
from loguru import logger

from app.utils.logger import config as configure_logger

# Ensure log configuration once
configure_logger()

# Shared router for all qBittorrent shim endpoints
router = APIRouter(prefix="/api/v2")

# Log effective path mapping once for operator clarity
try:
    from .common import public_save_path
    from app.config import DOWNLOAD_DIR

    logger.info(
        "qBittorrent shim: public save path='{}', internal download dir='{}'".format(
            public_save_path(), DOWNLOAD_DIR
        )
    )
except Exception:
    pass

# Import submodules to register routes on the shared router
from . import auth  # noqa: F401
from . import app_meta  # noqa: F401
from . import categories  # noqa: F401
from . import sync  # noqa: F401
from . import torrents  # noqa: F401
from . import transfer  # noqa: F401

__all__ = ["router"]
