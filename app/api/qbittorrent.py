from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Response, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlmodel import Session
from loguru import logger
from app.config import DOWNLOAD_DIR, QBIT_PUBLIC_SAVE_PATH
from app.magnet import parse_magnet
from app.models import (
    get_session,
    upsert_client_task,
    get_client_task,
    delete_client_task,
    get_job,
)
from app.scheduler import schedule_download, cancel_job

router = APIRouter(prefix="/api/v2")

from app.config import QBIT_PUBLIC_SAVE_PATH as _PUB

CATEGORIES: dict[str, dict] = {
    "prowlarr": {"name": "prowlarr", "savePath": _PUB or str(DOWNLOAD_DIR)}
}


# --- Auth endpoints (minimal)
@router.post("/auth/login")
def login(username: str = Form(default=""), password: str = Form(default="")):
    logger.info(f"Login attempt for user: {username}")
    # akzeptiere alles, setze Cookie wie qBittorrent
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


@router.post("/torrents/createCategory")
def torrents_create_category(
    category: str = Form(...),
    savePath: Optional[str] = Form(default=None),
):
    """
    Erstellt eine Kategorie. qBittorrent erwartet 200 OK bei Erfolg.
    """
    cat = category.strip()
    if not cat:
        raise HTTPException(status_code=400, detail="invalid category")
    CATEGORIES[cat] = {"name": cat, "savePath": savePath or str(DOWNLOAD_DIR)}
    logger.info(
        f"Created category '{cat}' with savePath='{CATEGORIES[cat]['savePath']}'"
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
        # qBittorrent erstellt stillschweigend oft — wir machen es genauso simpel:
        CATEGORIES[cat] = {"name": cat, "savePath": savePath or str(DOWNLOAD_DIR)}
    else:
        if savePath is not None:
            CATEGORIES[cat]["savePath"] = savePath
    logger.info(f"Edited category '{cat}' -> savePath='{CATEGORIES[cat]['savePath']}'")
    return PlainTextResponse("Ok.")


@router.post("/torrents/removeCategories")
def torrents_remove_categories(categories: str = Form(...)):
    """
    'categories' ist '|' getrennt.
    """
    count = 0
    for raw in categories.split("|"):
        cat = raw.strip()
        if cat in CATEGORIES:
            CATEGORIES.pop(cat, None)
            count += 1
    logger.info(f"Removed {count} categories")
    return PlainTextResponse("Ok.")


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
    """
    Minimaler Preferences-Dump, den Prowlarr/„qBittorrent“-Tests akzeptieren.
    Werte sind largely kosmetisch; wichtig ist ein gültiges JSON mit save_path.
    """
    logger.debug("App preferences requested.")
    from app.config import QBIT_PUBLIC_SAVE_PATH

    return JSONResponse(
        {
            # Pfade/Download-Verhalten
            "save_path": QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR),
            "temp_path_enabled": False,
            "temp_path": "",
            "create_subfolder_enabled": True,
            "start_paused_enabled": False,
            "auto_tmm_enabled": False,
            "disable_auto_tmm_by_default": True,
            # Kategorien-Verhalten (wir liefern Kategorien separat unter /torrents/categories)
            "torrent_content_layout": 0,  # 0=Original, 1=Create subfolder, 2=NoSubfolder (ab qB 4.3.2)
            # Netzwerk/BT (Dummy-Werte, aber plausibel)
            "listen_port": 6881,
            "dht": True,
            "pex": True,
            "lsd": True,
            # UI/sonstiges (irrelevant für Prowlarr, aber harmless)
            "web_ui_clickjacking_protection_enabled": True,
            "web_ui_csrf_protection_enabled": True,
            "web_ui_username": "admin",
        }
    )


@router.get("/torrents/categories")
def torrents_categories():
    """
    Liefert alle bekannten Kategorien zurück.
    Prowlarr braucht das beim Verbindungs-Test.
    """
    logger.debug("Torrents categories requested.")
    return JSONResponse(CATEGORIES)


@router.get("/sync/maindata")
def sync_maindata(session: Session = Depends(get_session)):
    """
    Minimaler Dump, der von Sonarr akzeptiert wird.
    """
    logger.debug("Sync maindata requested.")
    from sqlmodel import select
    from app.models import ClientTask, get_job  # get_job ist bereits importiert oben

    # Baue Torrent-Map wie qBittorrent (hash -> properties)
    rows = session.exec(select(ClientTask)).all()
    torrents: dict[str, dict] = {}
    import os
    import time

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
        # Derive size, save_path and completion time more accurately on completion
        size_val = int(job.total_bytes or 0) if job else 0
        save_path_val = r.save_path or (QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR))
        # Prefer directory of the actual file if we know it
        if job and job.result_path:
            try:
                import os

                real_dir = os.path.abspath(os.path.dirname(job.result_path))
                save_path_val = QBIT_PUBLIC_SAVE_PATH or real_dir
            except Exception:
                pass
        completion_ts = int((r.completion_on or r.added_on).timestamp())
        if job and job.status == "completed":
            # If result_path exists, prefer filesystem size
            if job.result_path and os.path.exists(job.result_path):
                try:
                    size_val = int(os.path.getsize(job.result_path))
                except Exception:
                    pass
            # Set completion_on if not already set
            if r.completion_on is None:
                r.completion_on = datetime.fromtimestamp(time.time(), tz=timezone.utc)
                try:
                    session.add(r)
                    session.commit()
                except Exception:
                    session.rollback()
                completion_ts = int(r.completion_on.timestamp())

        # If completed, don't report residual download speed
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
        }

    # rid kann einfach monoton sein; hier statisch/inkrementell nicht nötig
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


# --- Torrents API (Subset)


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
    Sonarr postet magnet URL(s) hierhin.
    """
    logger.info(f"Received request to add torrent(s): {urls}")
    if not urls:
        logger.warning("No URLs provided in torrents_add.")
        raise HTTPException(status_code=400, detail="missing urls")
    # es können mehrere URLs kommen, wir nehmen die erste
    magnet = urls.splitlines()[0].strip()
    logger.debug(f"Parsing magnet: {magnet}")
    payload = parse_magnet(magnet)

    slug = payload["aw_slug"]
    season = int(payload["aw_s"])
    episode = int(payload["aw_e"])
    language = payload["aw_lang"]
    name = payload.get("dn", f"{slug}.S{season:02d}E{episode:02d}.{language}")
    xt = payload["xt"]
    btih = xt.split(":")[-1].lower()

    logger.info(
        f"Scheduling download for {name} (slug={slug}, season={season}, episode={episode}, lang={language})"
    )
    # Job anwerfen
    req = {"slug": slug, "season": season, "episode": episode, "language": language}
    job_id = schedule_download(req)
    logger.debug(f"Scheduled job_id: {job_id}")

    # default save path if not provided
    if not savepath:
        savepath = str(DOWNLOAD_DIR)
    # path we publish to clients (may be overridden for container mapping)
    published_savepath = QBIT_PUBLIC_SAVE_PATH or savepath

    upsert_client_task(
        session,
        hash=btih,
        name=name,
        slug=slug,
        season=season,
        episode=episode,
        language=language,
        save_path=published_savepath,
        category=category,
        job_id=job_id,
        state="queued" if paused else "downloading",
    )
    logger.success(
        f"Torrent task upserted for hash={btih}, state={'queued' if paused else 'downloading'}"
    )
    return PlainTextResponse("Ok.")


@router.get("/torrents/info")
def torrents_info(
    session: Session = Depends(get_session),
    filter: Optional[str] = None,
    category: Optional[str] = None,
):
    """
    Liefert Liste der „Torrents“ (ClientTasks) im qBittorrent-Format (Subset).
    """
    logger.debug("Fetching torrents info.")
    # Wir geben alle zurück; Sonarr filtert clientseitig.
    # (Für echtes Filtering bräuchten wir eine Query/Migration; fürs MVP genügt das.)
    from sqlmodel import select
    from app.models import ClientTask

    import os
    import time

    rows = session.exec(select(ClientTask)).all()
    logger.info(f"Found {len(rows)} client tasks in database.")
    out: List[dict] = []
    for r in rows:
        if category and (r.category or "") != category:
            # Respect category filter like qBittorrent
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
                # prefer filesystem size if available
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

        # Compute content_path and save_path from the final file when known
        content_path = None
        save_path_val = r.save_path or (QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR))
        if job and job.result_path:
            try:
                # Normalize to absolute path for Sonarr
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
                "progress": progress,  # 0..1
                "dlspeed": dlspeed,  # bytes/sec
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
    """
    Minimal implementation of qBittorrent's /torrents/files.
    Returns a single-file list for our synthetic torrent with fields Sonarr uses.
    """
    from app.models import get_client_task
    import os

    h = (hash or "").strip().lower()
    if not h:
        raise HTTPException(status_code=400, detail="missing hash")
    rec = get_client_task(session, h)
    if not rec:
        raise HTTPException(status_code=404, detail="not found")

    job = get_job(session, rec.job_id) if rec.job_id else None
    # Derive file info
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
                # optional fields omitted by many clients; Sonarr doesn't require them
            }
        ]
    )


@router.get("/torrents/properties")
def torrents_properties(session: Session = Depends(get_session), hash: str = ""):
    """
    Minimal /torrents/properties implementation. Sonarr polls this after completion.
    We return a subset sufficient for Completed Download Handling.
    """
    from app.models import get_client_task
    import os
    import time

    h = (hash or "").strip().lower()
    if not h:
        raise HTTPException(status_code=400, detail="missing hash")
    rec = get_client_task(session, h)
    if not rec:
        raise HTTPException(status_code=404, detail="not found")

    job = get_job(session, rec.job_id) if rec.job_id else None
    # Prefer the directory of the final file if known
    save_path = rec.save_path or (QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR))
    total_size = 0
    if job and job.result_path and os.path.exists(job.result_path):
        try:
            total_size = int(os.path.getsize(job.result_path))
            if QBIT_PUBLIC_SAVE_PATH:
                save_path = QBIT_PUBLIC_SAVE_PATH
            else:
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
    """
    Entfernt Einträge; bricht laufende Jobs ab.
    """
    logger.info(f"Delete requested for hashes: {hashes}")
    for h in hashes.split("|"):
        h = h.strip().lower()
        rec = get_client_task(session, h)
        if rec and rec.job_id:
            logger.debug(f"Cancelling job {rec.job_id} for hash {h}")
            cancel_job(rec.job_id)
        delete_client_task(session, h)
        logger.success(f"Deleted client task for hash {h}")
    return PlainTextResponse("Ok.")


@router.get("/transfer/info")
def transfer_info():
    logger.debug("Transfer info requested.")
    # Kann statisch sein; Sonarr nutzt es kaum.
    return JSONResponse(
        {
            "dl_info_speed": 0,
            "up_info_speed": 0,
            "dl_info_data": 0,
            "up_info_data": 0,
        }
    )
