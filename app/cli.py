from __future__ import annotations

import os
import sys
from loguru import logger

from app.config import ANIBRIDGE_HOST, ANIBRIDGE_PORT, ANIBRIDGE_RELOAD


def run_server(app_obj):
    """Run the Uvicorn server with sensible defaults.

    - Enables reload by default in non-frozen (dev) runs
    - Disables reload for packaged/production runs
    - Allows override via ANIBRIDGE_RELOAD env/setting
    """
    import uvicorn

    is_frozen = getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")
    reload_env = os.environ.get("ANIBRIDGE_RELOAD") or ANIBRIDGE_RELOAD
    if reload_env is not None:
        reload_flag = reload_env == "1" or str(reload_env).lower() == "true"
    else:
        reload_flag = not is_frozen

    if reload_flag:
        logger.info("Uvicorn reload enabled (development mode).")
        uvicorn.run(
            "app.main:app",
            host=ANIBRIDGE_HOST,
            port=ANIBRIDGE_PORT,
            reload=True,
        )
    else:
        logger.info("Uvicorn reload disabled (packaged/production mode).")
        uvicorn.run(
            app_obj,
            host=ANIBRIDGE_HOST,
            port=ANIBRIDGE_PORT,
            reload=False,
        )

