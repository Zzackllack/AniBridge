from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Response, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlmodel import Session
from loguru import logger
from app.config import DOWNLOAD_DIR
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

CATEGORIES: dict[str, dict] = {
    "prowlarr": {"name": "prowlarr", "savePath": str(DOWNLOAD_DIR)}
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
    return JSONResponse(
        {
            # Pfade/Download-Verhalten
            "save_path": str(DOWNLOAD_DIR),
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
        torrents[r.hash] = {
            "name": r.name,
            "progress": progress,
            "state": state,
            "dlspeed": int(job.speed or 0) if job else 0,
            "eta": int(job.eta or 0) if job else 0,
            "category": r.category or "",
            "save_path": r.save_path or "",
            "size": int(job.total_bytes or 0) if job else 0,
            "added_on": int(r.added_on.timestamp()),
            "completion_on": int((r.completion_on or r.added_on).timestamp()),
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

    upsert_client_task(
        session,
        hash=btih,
        name=name,
        slug=slug,
        season=season,
        episode=episode,
        language=language,
        save_path=savepath,
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
            elif job.status == "failed":
                state = "error"
            elif job.status == "cancelled":
                state = "pausedDL"
            else:
                state = "downloading"

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
                "save_path": r.save_path or "",
                "added_on": int(r.added_on.timestamp()),
                "completion_on": int((r.completion_on or r.added_on).timestamp()),
                "size": int(size or 0),
                "num_seeds": 0,
                "num_leechs": 0,
            }
        )
    logger.success("Torrent info response generated.")
    return JSONResponse(out)


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
