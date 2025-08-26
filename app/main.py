import sys
import os
import uuid
import errno
import asyncio
import threading
from loguru import logger
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from app.infrastructure.terminal_logger import TerminalLogger
from app.utils.logger import config as configure_logger, ensure_log_path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pathlib import Path
from sqlmodel import Session
from app.config import DOWNLOAD_DIR
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, Future
from app.api.torznab import router as torznab_router
from app.api.qbittorrent import router as qbittorrent_router
from app.core.scheduler import init_executor, shutdown_executor, schedule_download
from app.core.scheduler import RUNNING, RUNNING_LOCK
from app.core.downloader import (
    LanguageUnavailableError,
    Provider,
    Language,
    download_episode,
)
from app.models import (
    Job,
    get_session,
    create_db_and_tables,
    cleanup_dangling_jobs,
    create_job,
    get_job as db_get_job,
    update_job as db_update_job,
    engine,
)

load_dotenv()
configure_logger()
# Ensure ANIBRIDGE_LOG_PATH is set and data dir exists. We keep the
# TerminalLogger instantiation here to avoid import cycles between app
# packages (TerminalLogger may import app.utils.logger indirectly).
ensure_log_path()
TerminalLogger(Path.cwd() / "data")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global EXECUTOR
    logger.info("Application startup: creating DB and thread pool executor.")
    create_db_and_tables()
    with Session(engine) as s:
        cleaned = cleanup_dangling_jobs(s)
        if cleaned:
            logger.info(f"Reset {cleaned} dangling jobs to 'failed'")
    init_executor()
    yield
    shutdown_executor()


app = FastAPI(title="AniBridge-Minimal", lifespan=lifespan)
app.include_router(torznab_router)  # Torznab feed
app.include_router(qbittorrent_router)  # qBittorrent shim


# Healthcheck endpoint for CI/CD and monitoring
@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


# --- Legacy direct downloader endpoint (bleibt nutzbar)
class DownloadRequest(BaseModel):
    link: str | None = Field(default=None)
    slug: str | None = Field(default=None)
    season: int | None = None
    episode: int | None = None
    provider: Provider | None = "VOE"
    language: Language = "German Dub"
    title_hint: str | None = None


class EnqueueResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    id: str
    status: str
    progress: float
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: int | None = None
    message: str | None = None
    result_path: str | None = None


def _progress_updater(job_id: str, stop_event: threading.Event):
    from tqdm import tqdm

    bar = None

    def _cb(d: dict):
        nonlocal bar
        if stop_event.is_set():
            if bar is not None:
                bar.close()
            logger.warning(f"Job {job_id} cancelled by stop_event.")
            raise Exception("Cancelled")
        status = d.get("status")
        downloaded = int(d.get("downloaded_bytes") or 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        speed = d.get("speed")
        eta = d.get("eta")

        progress = 0.0
        if total:
            try:
                progress = max(0.0, min(100.0, downloaded / total * 100.0))
            except Exception as e:
                logger.error(f"Progress calculation error: {e}")

        if bar is None and total:
            bar = tqdm(
                total=int(total),
                desc=f"Job {job_id}",
                unit="B",
                unit_scale=True,
                leave=True,
            )
        if bar is not None:
            bar.n = downloaded
            bar.set_postfix(
                {
                    "Speed": f"{float(speed)/(1024*1024):.2f} MB/s" if speed else "-",
                    "ETA": f"{float(eta):.2f}s" if eta else "-",
                }
            )
            bar.refresh()

        # throttle DB writes: etwa 1% Schritte
        if bar is not None and (
            bar.n == bar.total or bar.n % max(1, bar.total // 100) == 0
        ):
            with Session(engine) as s:
                db_update_job(
                    s,
                    job_id,
                    status="downloading" if status != "finished" else "downloading",
                    downloaded_bytes=downloaded,
                    total_bytes=int(total) if total else None,
                    speed=float(speed) if speed else None,
                    eta=int(eta) if eta else None,
                    progress=progress,
                )
        if status == "finished" and bar is not None:
            bar.n = bar.total
            bar.refresh()
            bar.close()

    return _cb


def _run_download(job_id: str, req: DownloadRequest, stop_event: threading.Event):
    logger.info(f"Starting download job {job_id} with request: {req}")
    try:
        with Session(engine) as s:
            db_update_job(s, job_id, status="downloading", message=None)

        dest = download_episode(
            link=req.link,
            slug=req.slug,
            season=req.season,
            episode=req.episode,
            provider=req.provider,
            language=req.language,
            dest_dir=DOWNLOAD_DIR,
            title_hint=req.title_hint,
            progress_cb=_progress_updater(job_id, stop_event),
            stop_event=stop_event,
        )

        # Only log and update job once after process finishes
        logger.success(f"Download job {job_id} completed. File: {dest}")
        with Session(engine) as s:
            db_update_job(
                s, job_id, status="completed", progress=100.0, result_path=str(dest)
            )

    except LanguageUnavailableError as le:
        # klare, nutzerfreundliche Fehlermeldung
        msg = f"Sprache nicht verfügbar: '{le.requested}'. Verfügbar: {', '.join(le.available) or '—'}"
        logger.error(f"LanguageUnavailableError in job {job_id}: {msg}")
        with Session(engine) as s:
            db_update_job(s, job_id, status="failed", message=msg)

    except OSError as e:
        logger.error(f"OSError in job {job_id}: {e}")
        with Session(engine) as s:
            if e.errno in (errno.EACCES, errno.EROFS):
                db_update_job(
                    s,
                    job_id,
                    status="failed",
                    message=f"Download dir not writable: {e}",
                )
            else:
                db_update_job(s, job_id, status="failed", message=str(e))
    except Exception as e:
        msg = str(e)
        status = "failed"
        if "Cancel" in msg or "cancel" in msg:
            status = "cancelled"
            msg = "Cancelled by user"
        logger.error(f"Exception in job {job_id}: {msg}")
        with Session(engine) as s:
            db_update_job(s, job_id, status=status, message=msg)
    finally:
        logger.info(f"Cleaning up job {job_id} from RUNNING registry.")
        with RUNNING_LOCK:
            RUNNING.pop(job_id, None)


@asynccontextmanager
async def _dummy(app: FastAPI):
    yield


@app.post("/downloader/download", response_model=EnqueueResponse)
def enqueue_download(req: DownloadRequest, session: Session = Depends(get_session)):
    # nutzt gemeinsamen Scheduler
    job_id = schedule_download(req.model_dump())
    return EnqueueResponse(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, session: Session = Depends(get_session)):
    job = db_get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        progress=job.progress,
        downloaded_bytes=job.downloaded_bytes,
        total_bytes=job.total_bytes,
        speed=job.speed,
        eta=job.eta,
        message=job.message,
        result_path=job.result_path,
    )


@app.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str, request: Request, session: Session = Depends(get_session)
):
    async def eventgen():
        last = None
        while True:
            if await request.is_disconnected():
                break
            job = db_get_job(session, job_id)
            if not job:
                yield "event: error\ndata: not_found\n\n"
                break
            payload = {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "downloaded_bytes": job.downloaded_bytes,
                "total_bytes": job.total_bytes,
                "speed": job.speed,
                "eta": job.eta,
                "message": job.message,
                "result_path": job.result_path,
            }
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if job.status in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(eventgen(), media_type="text/event-stream")


@app.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    """
    Bricht einen laufenden/queued Job ab (best effort).
    """
    with RUNNING_LOCK:
        item = RUNNING.get(job_id)
    if not item:
        return {"status": "not-running"}
    fut, ev = item
    ev.set()
    fut.cancel()
    return {"status": "cancelling"}


if __name__ == "__main__":
    logger.info("Starting AniBridge FastAPI server...")
    import uvicorn

    # When running as a PyInstaller one-file binary, sys.frozen/_MEIPASS
    # will be present. Uvicorn's reload/watchers spawn subprocesses and
    # pass special multiprocessing arguments to the executable which our
    # CLI argparse does not understand. Disable reload in packaged runs.
    is_frozen = getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")
    # Allow override via env var for advanced cases (set ANIBRIDGE_RELOAD=1 to force)
    reload_env = os.environ.get("ANIBRIDGE_RELOAD")
    if reload_env is not None:
        reload_flag = reload_env == "1"
    else:
        reload_flag = not is_frozen

    if reload_flag:
        logger.info("Uvicorn reload enabled (development mode).")
    else:
        logger.info("Uvicorn reload disabled (packaged/production mode).")

    # If reload is enabled (development), uvicorn expects an import string so
    # the reloader can import the module. When reload is disabled (packaged
    # binary), pass the app object directly to avoid import errors inside the
    # frozen executable.
    if reload_flag:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
        )
    else:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,
        )
