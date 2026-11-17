"""Legacy sync and torrent-list routes must agree on lifecycle and availability."""

from fastapi import Depends
from fastapi.responses import JSONResponse
from loguru import logger
from sqlmodel import Session, select

from app.db import ClientTask, get_job, get_session

from . import router
from .common import CATEGORIES
from .projection import torrent_info_record


@router.get("/sync/maindata")
def sync_maindata(session: Session = Depends(get_session)):
    logger.debug("Sync maindata requested.")
    torrents = {}
    for alias in session.exec(select(ClientTask)):
        job = get_job(session, alias.job_id) if alias.job_id else None
        # A read must not invent or commit completion timestamps. The shared
        # projection also keeps missing-file warnings consistent with info.
        torrents[alias.hash] = torrent_info_record(alias, job)
    return JSONResponse(
        {
            "rid": 1,
            "full_update": True,
            "server_state": {"connection_status": "connected", "dht_nodes": 1},
            "torrents": torrents,
            "categories": CATEGORIES,
        }
    )
