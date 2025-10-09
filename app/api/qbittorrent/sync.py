from __future__ import annotations

from fastapi import Depends
from fastapi.responses import JSONResponse
from loguru import logger
from sqlmodel import Session

from app.db import get_session, get_job

from . import router
from .common import CATEGORIES, public_save_path
from app.config import DOWNLOAD_DIR, QBIT_PUBLIC_SAVE_PATH


@router.get("/sync/maindata")
def sync_maindata(session: Session = Depends(get_session)):
    """Minimal maindata dump accepted by Sonarr."""
    logger.debug("Sync maindata requested.")
    from sqlmodel import select
    from app.db import ClientTask
    import os
    import time

    rows = session.exec(select(ClientTask)).all()
    torrents: dict[str, dict] = {}

    for r in rows:
        job = get_job(session, r.job_id) if r.job_id else None
        progress = (job.progress or 0.0) / 100.0 if job else 0.0
        state = "downloading"
        if job:
            if job.status == "completed":
                state = "uploading"
            elif job.status == "failed":
                state = "error"
            elif job.status == "cancelled":
                state = "pausedDL"

        size_val = int(job.total_bytes or 0) if job else 0
        save_path_val = (
            public_save_path()
            if QBIT_PUBLIC_SAVE_PATH
            else (r.save_path or str(DOWNLOAD_DIR))
        )

        if job and job.result_path:
            try:
                real_dir = os.path.abspath(os.path.dirname(job.result_path))
                save_path_val = QBIT_PUBLIC_SAVE_PATH or real_dir
            except Exception:
                pass

        completion_ts = int((r.completion_on or r.added_on).timestamp())
        if job and job.status == "completed":
            if job.result_path and os.path.exists(job.result_path):
                try:
                    size_val = int(os.path.getsize(job.result_path))
                except Exception:
                    pass
            if r.completion_on is None:
                r.completion_on = datetime.fromtimestamp(time.time(), tz=timezone.utc)  # type: ignore[name-defined]
                try:
                    session.add(r)
                    session.commit()
                except Exception:
                    session.rollback()
                completion_ts = int(r.completion_on.timestamp())

        dlspeed_val = int(job.speed or 0) if job else 0
        if job and job.status == "completed":
            dlspeed_val = 0

        torrents[r.hash] = {
            "name": r.name,
            "progress": progress,
            "state": state,
            "dlspeed": dlspeed_val,
            "eta": int(job.eta or 0) if job else 0,
            "category": r.category or "",
            "save_path": save_path_val,
            "size": size_val,
            "added_on": int(r.added_on.timestamp()),
            "completion_on": completion_ts,
            "anibridgeAbsolute": r.absolute_number,
        }

    return JSONResponse(
        {
            "rid": 1,
            "server_state": {
                "connection_status": "connected",
                "dht_nodes": 1,
            },
            "torrents": torrents,
            "categories": CATEGORIES,
        }
    )


# Required imports for datetime after function since we used it above
from datetime import datetime, timezone  # noqa: E402
