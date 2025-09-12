from __future__ import annotations

from fastapi import Form
from fastapi.responses import PlainTextResponse
from loguru import logger

from . import router


@router.post("/auth/login")
def login(username: str = Form(default=""), password: str = Form(default="")):
    logger.info(f"Login attempt for user: {username}")
    # accept all, set cookie like qBittorrent
    resp = PlainTextResponse("Ok.")
    resp.set_cookie("SID", "anibridge", httponly=True)
    logger.success("Login successful, SID cookie set.")
    return resp


@router.post("/auth/logout")
def logout():
    logger.info("Logout requested.")
    resp = PlainTextResponse("Ok.")
    resp.delete_cookie("SID")
    logger.success("Logout successful, SID cookie deleted.")
    return resp
