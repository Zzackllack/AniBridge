from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import PlainTextResponse
from loguru import logger

from . import router


@router.post("/auth/login")
def login(
    request: Request, username: str = Form(default=""), password: str = Form(default="")
):
    auth = request.app.state.qbit_auth
    if auth.enabled:
        request.session.clear()
        if not auth.credentials_match(username, password):
            logger.info("qBittorrent login rejected")
            return PlainTextResponse("Fails.", status_code=403)
        request.session["authenticated"] = True
        return PlainTextResponse("Ok.")
    # Compatibility mode remains restricted to a trusted private network.
    resp = PlainTextResponse("Ok.")
    resp.set_cookie("SID", "anibridge", httponly=True)
    logger.success("Login successful, SID cookie set.")
    return resp


@router.post("/auth/logout")
def logout(request: Request):
    logger.info("Logout requested.")
    resp = PlainTextResponse("Ok.")
    if request.app.state.qbit_auth.enabled:
        request.session.clear()
        return resp
    resp.delete_cookie("SID")
    logger.success("Logout successful, SID cookie deleted.")
    return resp
