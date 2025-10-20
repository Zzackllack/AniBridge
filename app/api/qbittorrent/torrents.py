from __future__ import annotations

from typing import List, Optional

from datetime import datetime, timezone
from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger
from sqlmodel import Session

from app.config import (
    DOWNLOAD_DIR,
    QBIT_PUBLIC_SAVE_PATH,
    DELETE_FILES_ON_TORRENT_DELETE,
)
from app.utils.magnet import parse_magnet
from app.db import (
    get_session,
    upsert_client_task,
    get_client_task,
    delete_client_task,
    get_job,
)
from app.core.scheduler import schedule_download, cancel_job

from . import router
from .common import public_save_path


@router.post("/torrents/add")
def torrents_add(
    request: Request,
    session: Session = Depends(get_session),
    urls: str = Form(default=""),
    savepath: Optional[str] = Form(default=None),
    category: Optional[str] = Form(default=None),
    paused: Optional[bool] = Form(default=False),
    tags: Optional[str] = Form(default=None),
):
    """
    Accept a Sonarr POST of magnet URL(s), schedule the download for the first magnet, and record a ClientTask.

    Parses the first magnet line from `urls`, extracts metadata (slug, season, episode, language, site, name, and torrent hash), schedules a download job, and upserts a ClientTask with the job and save path. If `savepath` is not provided, the configured download directory is used; if a public save path is configured it is stored as the task's save path.

    Parameters:
        urls (str): One or more magnet URLs separated by newlines; only the first line is processed.
        savepath (Optional[str]): Optional explicit save directory for the torrent. If omitted, the configured DOWNLOAD_DIR is used; a configured QBIT_PUBLIC_SAVE_PATH will be preferred when stored.
        category (Optional[str]): Optional category to record with the task.
        paused (Optional[bool]): If true, the created task is marked as queued instead of downloading.
        tags (Optional[str]): Optional tags provided by the caller (accepted but not otherwise interpreted here).

    Returns:
        PlainTextResponse: A plain-text response with the body "Ok." on success.

    Raises:
        HTTPException: Raised with status 400 when `urls` is empty or missing.
    """
    logger.info(f"Received request to add torrent(s): {urls}")
    if not urls:
        logger.warning("No URLs provided in torrents_add.")
        raise HTTPException(status_code=400, detail="missing urls")

    magnet = urls.splitlines()[0].strip()
    logger.debug(f"Parsing magnet: {magnet}")
    try:
        payload = parse_magnet(magnet)
        prefix = "aw" if "aw_slug" in payload else "sto"

        slug = payload[f"{prefix}_slug"]
        season = int(payload[f"{prefix}_s"])
        episode = int(payload[f"{prefix}_e"])
        language = payload[f"{prefix}_lang"]
        site = payload.get(f"{prefix}_site", "aniworld.to" if prefix == "aw" else "s.to")
        name = payload.get("dn", f"{slug}.S{season:02d}E{episode:02d}.{language}")
        xt = payload["xt"]
    except (KeyError, ValueError) as exc:
        logger.warning(f"Malformed magnet parameters: {exc}")
        raise HTTPException(status_code=400, detail="malformed magnet parameters") from exc

    btih = xt.split(":")[-1].lower()

    logger.info(
        "Scheduling download for {} (slug={}, season={}, episode={}, lang={}, site={})".format(
            name, slug, season, episode, language, site
        )
    )

    req = {
        "slug": slug,
        "season": season,
        "episode": episode,
        "language": language,
        "site": site,
    }
    job_id = schedule_download(req)
    logger.debug(f"Scheduled job_id: {job_id}")

    if not savepath:
        savepath = str(DOWNLOAD_DIR)
    published_savepath = QBIT_PUBLIC_SAVE_PATH or savepath

    upsert_client_task(
        session,
        hash=btih,
        name=name,
        slug=slug,
        season=season,
        episode=episode,
        language=language,
        site=site,
        save_path=published_savepath,
        category=category,
        job_id=job_id,
        state="queued" if paused else "downloading",
    )
    logger.success(
        "Torrent task upserted for hash={}, state={}, site={}".format(
            btih, "queued" if paused else "downloading", site
        )
    )
    return PlainTextResponse("Ok.")


@router.get("/torrents/info")
def torrents_info(
    session: Session = Depends(get_session),
    filter: Optional[str] = None,
    category: Optional[str] = None,
):
    """List torrents (ClientTasks) in qBittorrent-compatible subset."""
    logger.debug("Fetching torrents info.")
    from sqlmodel import select
    from app.db import ClientTask
    import os

    rows = session.exec(select(ClientTask)).all()
    logger.info(f"Found {len(rows)} client tasks in database.")
    out: List[dict] = []
    for r in rows:
        if category and (r.category or "") != category:
            continue
        job = get_job(session, r.job_id) if r.job_id else None
        state = r.state
        progress = 0.0
        dlspeed = 0
        eta = 0
        size = job.total_bytes if job and job.total_bytes else 0
        if job:
            progress = (job.progress or 0.0) / 100.0
            dlspeed = int(job.speed or 0)
            eta = int(job.eta or 0)
            logger.debug(
                f"Job {job.id}: status={job.status}, progress={progress}, speed={dlspeed}, eta={eta}"
            )
            if job.status == "completed":
                state = "uploading"
                dlspeed = 0
                if job.result_path and os.path.exists(job.result_path):
                    try:
                        size = int(os.path.getsize(job.result_path))
                    except Exception:
                        pass
            elif job.status == "failed":
                state = "error"
            elif job.status == "cancelled":
                state = "pausedDL"
            else:
                state = "downloading"

        content_path = None
        save_path_val = r.save_path or (QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR))
        if job and job.result_path:
            try:
                import os

                content_abs = os.path.abspath(job.result_path)
                if QBIT_PUBLIC_SAVE_PATH:
                    content_path = os.path.join(
                        QBIT_PUBLIC_SAVE_PATH, os.path.basename(content_abs)
                    )
                    save_path_val = QBIT_PUBLIC_SAVE_PATH
                else:
                    content_path = content_abs
                    save_path_val = os.path.abspath(os.path.dirname(content_abs))
            except Exception:
                content_path = job.result_path

        out.append(
            {
                "hash": r.hash,
                "name": r.name,
                "state": state,
                "progress": progress,
                "dlspeed": dlspeed,
                "upspeed": 0,
                "eta": eta,
                "category": r.category or "",
                "save_path": save_path_val,
                "content_path": content_path or "",
                "added_on": int(r.added_on.timestamp()),
                "completion_on": int((r.completion_on or r.added_on).timestamp()),
                "size": int(size or 0),
                "num_seeds": 0,
                "num_leechs": 0,
            }
        )
    logger.success("Torrent info response generated.")
    return JSONResponse(out)


@router.get("/torrents/files")
def torrents_files(session: Session = Depends(get_session), hash: str = ""):
    """Minimal implementation of /torrents/files returning a single-file list."""
    import os

    h = (hash or "").strip().lower()
    if not h:
        raise HTTPException(status_code=400, detail="missing hash")
    rec = get_client_task(session, h)
    if not rec:
        raise HTTPException(status_code=404, detail="not found")

    job = get_job(session, rec.job_id) if rec.job_id else None
    file_name = rec.name
    size = 0
    prog = 0.0
    is_seed = False
    if job:
        prog = (job.progress or 0.0) / 100.0
        if job.result_path and os.path.exists(job.result_path):
            try:
                size = int(os.path.getsize(job.result_path))
                file_name = os.path.basename(job.result_path)
            except Exception:
                pass
        if job.status == "completed":
            prog = 1.0
            is_seed = True

    return JSONResponse(
        [
            {
                "index": 0,
                "name": file_name,
                "size": int(size or 0),
                "progress": float(prog),
                "priority": 1,
                "is_seed": is_seed,
            }
        ]
    )


@router.get("/torrents/properties")
def torrents_properties(session: Session = Depends(get_session), hash: str = ""):
    """Minimal /torrents/properties implementation used by Sonarr after completion."""
    import os
    import time

    h = (hash or "").strip().lower()
    if not h:
        raise HTTPException(status_code=400, detail="missing hash")
    rec = get_client_task(session, h)
    if not rec:
        raise HTTPException(status_code=404, detail="not found")

    job = get_job(session, rec.job_id) if rec.job_id else None
    save_path = public_save_path()
    total_size = 0
    if job and job.result_path and os.path.exists(job.result_path):
        try:
            total_size = int(os.path.getsize(job.result_path))
            if not QBIT_PUBLIC_SAVE_PATH:
                save_path = os.path.abspath(os.path.dirname(job.result_path))
        except Exception:
            total_size = int(job.total_bytes or 0)
    elif job and job.total_bytes:
        total_size = int(job.total_bytes)

    now = int(time.time())
    addition_date = int(rec.added_on.timestamp())
    completion_date = int((rec.completion_on or rec.added_on).timestamp())
    seeding_time = max(0, now - completion_date) if rec.completion_on else 0
    time_elapsed = max(0, now - addition_date)

    return JSONResponse(
        {
            "save_path": save_path,
            "creation_date": addition_date,
            "piece_size": total_size or 1,
            "pieces_have": 1 if job and job.status == "completed" else 0,
            "pieces_num": 1,
            "dl_limit": 0,
            "up_limit": 0,
            "total_wasted": 0,
            "total_uploaded": 0,
            "total_uploaded_session": 0,
            "total_downloaded": total_size,
            "total_downloaded_session": total_size,
            "up_speed_avg": 0,
            "dl_speed_avg": 0,
            "time_elapsed": time_elapsed,
            "seeding_time": seeding_time,
            "nb_connections": 0,
            "nb_connections_limit": 0,
            "share_ratio": 0,
            "addition_date": addition_date,
            "completion_date": completion_date,
            "created_by": "AniBridge",
            "last_seen": 0,
            "total_seen": 0,
        }
    )


@router.post("/torrents/delete")
def torrents_delete(
    session: Session = Depends(get_session),
    hashes: str = Form(...),
    deleteFiles: Optional[bool] = Form(default=False),
):
    """Remove entries; cancel running jobs and optionally delete files."""
    effective_delete = bool(deleteFiles) or bool(DELETE_FILES_ON_TORRENT_DELETE)
    logger.info(
        f"Delete requested for hashes: {hashes}, deleteFiles={deleteFiles}, effective={effective_delete}"
    )
    for h in hashes.split("|"):
        h = h.strip().lower()
        rec = get_client_task(session, h)
        if rec and rec.job_id:
            logger.debug(f"Cancelling job {rec.job_id} for hash {h}")
            cancel_job(rec.job_id)
        try:
            if effective_delete:
                job = get_job(session, rec.job_id) if (rec and rec.job_id) else None
                if job and job.result_path:
                    import os

                    p = job.result_path
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                            logger.success(f"Deleted file for hash {h}: {p}")
                        except Exception as e:
                            logger.warning(f"Failed to delete file for hash {h}: {e}")
                    try:
                        parent = os.path.dirname(p)
                        if parent and os.path.isdir(parent) and not os.listdir(parent):
                            os.rmdir(parent)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Exception during file deletion for hash {h}: {e}")
        delete_client_task(session, h)
        logger.success(f"Deleted client task for hash {h}")
    return PlainTextResponse("Ok.")
