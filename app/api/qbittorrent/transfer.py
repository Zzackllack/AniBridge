from __future__ import annotations

from fastapi.responses import JSONResponse
from loguru import logger

from . import router


@router.get("/transfer/info")
def transfer_info():
    logger.debug("Transfer info requested.")
    return JSONResponse(
        {
            "dl_info_speed": 0,
            "up_info_speed": 0,
            "dl_info_data": 0,
            "up_info_data": 0,
        }
    )
