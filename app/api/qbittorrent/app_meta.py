from __future__ import annotations

from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger

from . import router
from .common import public_save_path


@router.get("/app/version")
def app_version():
    logger.debug("App version requested.")
    return PlainTextResponse("4.6.0")


@router.get("/app/webapiVersion")
def webapi_version():
    logger.debug("WebAPI version requested.")
    return PlainTextResponse("2.8.18")


@router.get("/app/buildInfo")
def app_build_info():
    logger.debug("App build info requested.")
    return JSONResponse(
        {
            "qt": "5.15.2",
            "libtorrent": "2.0.9",
            "boost": "1.78.0",
            "openssl": "3.0.0",
            "bitness": 64,
        }
    )


@router.get("/app/preferences")
def app_preferences():
    logger.debug("App preferences requested.")
    # Minimal preferences dump that Prowlarr/clients accept
    return JSONResponse(
        {
            # Paths / download behavior
            "save_path": public_save_path(),
            "temp_path_enabled": False,
            "temp_path": "",
            "create_subfolder_enabled": True,
            "start_paused_enabled": False,
            "auto_tmm_enabled": False,
            "disable_auto_tmm_by_default": True,
            # Category behavior
            "torrent_content_layout": 0,  # 0=Original, 1=Create subfolder, 2=NoSubfolder
            # Network/BT (dummy but plausible)
            "listen_port": 6881,
            "dht": True,
            "pex": True,
            "lsd": True,
            # UI/misc (harmless)
            "web_ui_clickjacking_protection_enabled": True,
            "web_ui_csrf_protection_enabled": True,
            "web_ui_username": "admin",
        }
    )
