from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Response, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlmodel import Session
from loguru import logger

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


@router.get("/app/version")
def app_version():
    logger.debug("App version requested.")
    return PlainTextResponse("4.6.0")


@router.get("/app/webapiVersion")
def webapi_version():
    logger.debug("WebAPI version requested.")
    return PlainTextResponse("2.8.18")


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

    logger.info(f"Scheduling download for {name} (slug={slug}, season={season}, episode={episode}, lang={language})")
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
    logger.success(f"Torrent task upserted for hash={btih}, state={'queued' if paused else 'downloading'}")
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
            logger.debug(f"Job {job.id}: status={job.status}, progress={progress}, speed={dlspeed}, eta={eta}")
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
