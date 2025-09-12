from __future__ import annotations

from typing import Optional

from fastapi import Form, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger

from app.config import DOWNLOAD_DIR

from . import router
from .common import CATEGORIES


@router.post("/torrents/createCategory")
def torrents_create_category(
    category: str = Form(...),
    savePath: Optional[str] = Form(default=None),
):
    """Create a category. qBittorrent expects 200 OK on success."""
    cat = category.strip()
    if not cat:
        raise HTTPException(status_code=400, detail="invalid category")
    CATEGORIES[cat] = {"name": cat, "savePath": savePath or str(DOWNLOAD_DIR)}
    logger.info(
        "Created category '{}' with savePath='{}'".format(
            cat, CATEGORIES[cat]["savePath"]
        )
    )
    return PlainTextResponse("Ok.")


@router.post("/torrents/editCategory")
def torrents_edit_category(
    category: str = Form(...),
    savePath: Optional[str] = Form(default=None),
):
    cat = category.strip()
    if not cat:
        raise HTTPException(status_code=400, detail="invalid category")
    if cat not in CATEGORIES:
        # qBittorrent often creates silently — mimic simply
        CATEGORIES[cat] = {"name": cat, "savePath": savePath or str(DOWNLOAD_DIR)}
    else:
        if savePath is not None:
            CATEGORIES[cat]["savePath"] = savePath
    logger.info("Edited category '{}' -> savePath='{}'".format(cat, CATEGORIES[cat]["savePath"]))
    return PlainTextResponse("Ok.")


@router.post("/torrents/removeCategories")
def torrents_remove_categories(categories: str = Form(...)):
    """'categories' is '|' separated."""
    count = 0
    for raw in categories.split("|"):
        cat = raw.strip()
        if cat in CATEGORIES:
            CATEGORIES.pop(cat, None)
            count += 1
    logger.info(f"Removed {count} categories")
    return PlainTextResponse("Ok.")


@router.get("/torrents/categories")
def torrents_categories():
    """Return all known categories; used by Prowlarr connection test."""
    logger.debug("Torrents categories requested.")
    return JSONResponse(CATEGORIES)

