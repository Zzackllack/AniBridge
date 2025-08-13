from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pathlib import Path
from sqlmodel import Session
import errno
import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, Future
import threading

from app.downloader import download_episode, Provider, Language
from app.config import DOWNLOAD_DIR, MAX_CONCURRENCY
from app.models import (
    Job, get_session, create_db_and_tables, cleanup_dangling_jobs,
    create_job, get_job as db_get_job, update_job as db_update_job, engine
)

# ---- Thread-Pool und Cancel-Registry ----
EXECUTOR: ThreadPoolExecutor | None = None
RUNNING: dict[str, tuple[Future, threading.Event]] = {}
RUNNING_LOCK = threading.Lock()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global EXECUTOR
    # Startup
    create_db_and_tables()
    with Session(engine) as s:
        cleaned = cleanup_dangling_jobs(s)
        if cleaned:
            print(f"[startup] Reset {cleaned} dangling jobs to 'failed'")
    EXECUTOR = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="anibridge")
    print(f"[startup] ThreadPoolExecutor started with max_workers={MAX_CONCURRENCY}")
    yield
    # Shutdown: Executor schließen, laufende Jobs canceln
    with RUNNING_LOCK:
        for job_id, (fut, ev) in RUNNING.items():
            ev.set()
        RUNNING.clear()
    if EXECUTOR:
        EXECUTOR.shutdown(wait=False, cancel_futures=True)
        print("[shutdown] Executor shutdown requested")

app = FastAPI(title="AniBridge-Minimal", lifespan=lifespan)

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
    last = {"downloaded": 0, "total": 0, "speed": 0.0, "eta": 0}
    def _cb(d: dict):
        # Cancel frühzeitig?
        if stop_event.is_set():
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
            except Exception:
                pass

        if (
            last["downloaded"] != downloaded or
            last["total"] != total or
            last["speed"] != speed or
            last["eta"] != eta
        ):
            mb_speed = float(speed) / (1024 * 1024) if speed else 0.0
            print(f"[{job_id}] {progress:.2f}% {mb_speed:.2f} MB/s ETA {float(eta) if eta else 0:.2f}s")
            last.update(downloaded=downloaded, total=total, speed=speed, eta=eta)

        with Session(engine) as s:
            db_update_job(
                s, job_id,
                status="downloading" if status != "finished" else "downloading",
                downloaded_bytes=downloaded,
                total_bytes=int(total) if total else None,
                speed=float(speed) if speed else None,
                eta=int(eta) if eta else None,
                progress=progress,
            )
    return _cb

def _run_download(job_id: str, req: DownloadRequest, stop_event: threading.Event):
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

        with Session(engine) as s:
            db_update_job(s, job_id, status="completed", progress=100.0, result_path=str(dest))
    except OSError as e:
        with Session(engine) as s:
            if e.errno in (errno.EACCES, errno.EROFS):
                db_update_job(s, job_id, status="failed", message=f"Download dir not writable: {e}")
            else:
                db_update_job(s, job_id, status="failed", message=str(e))
    except Exception as e:
        msg = str(e)
        status = "failed"
        if "Cancel" in msg or "cancel" in msg:
            status = "cancelled"
            msg = "Cancelled by user"
        with Session(engine) as s:
            db_update_job(s, job_id, status=status, message=msg)
    finally:
        # aus RUNNING austragen
        with RUNNING_LOCK:
            RUNNING.pop(job_id, None)

@app.post("/downloader/download", response_model=EnqueueResponse)
def enqueue_download(req: DownloadRequest, session: Session = Depends(get_session)):
    if EXECUTOR is None:
        raise HTTPException(status_code=500, detail="Executor not initialized")
    job = create_job(session)
    stop_event = threading.Event()
    fut = EXECUTOR.submit(_run_download, job.id, req, stop_event)
    with RUNNING_LOCK:
        RUNNING[job.id] = (fut, stop_event)
    return EnqueueResponse(job_id=job.id)

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
async def job_events(job_id: str, request: Request, session: Session = Depends(get_session)):
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
        # evtl. schon fertig/fehlgeschlagen/nicht vorhanden
        return {"status": "not-running"}
    fut, ev = item
    ev.set()           # signalisiere Cancel
    fut.cancel()       # falls noch nicht gestartet
    return {"status": "cancelling"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
