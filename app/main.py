from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pathlib import Path
from app.downloader import download_episode, Provider, Language
from app.config import DOWNLOAD_DIR
from app.models import store, Job
import errno
import asyncio

app = FastAPI(title="AniBridge-Minimal")

class DownloadRequest(BaseModel):
    link: str | None = Field(default=None)
    slug: str | None = Field(default=None)
    season: int | None = None
    episode: int | None = None
    provider: Provider = "VOE"
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

def _progress_updater(job_id: str):
    def _cb(d: dict):
        # yt-dlp states: 'downloading', 'finished', 'error'
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

        store.update(job_id,
                     status="downloading" if status != "finished" else "downloading",
                     downloaded_bytes=downloaded,
                     total_bytes=int(total) if total else None,
                     speed=float(speed) if speed else None,
                     eta=int(eta) if eta else None,
                     progress=progress)
    return _cb

def _run_download(job_id: str, req: DownloadRequest):
    try:
        store.update(job_id, status="downloading", message=None)
        dest = download_episode(
            link=req.link,
            slug=req.slug,
            season=req.season,
            episode=req.episode,
            provider=req.provider,
            language=req.language,
            dest_dir=DOWNLOAD_DIR,
            title_hint=req.title_hint,
            progress_cb=_progress_updater(job_id),
        )
        store.update(job_id, status="completed", progress=100.0, result_path=dest)
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EROFS):
            store.update(job_id, status="failed", message=f"Download dir not writable: {e}")
        else:
            store.update(job_id, status="failed", message=str(e))
    except Exception as e:
        store.update(job_id, status="failed", message=str(e))

@app.post("/downloader/download", response_model=EnqueueResponse)
def enqueue_download(req: DownloadRequest, background: BackgroundTasks):
    # sofort Job anlegen, NICHT blockieren
    job = store.create()
    background.add_task(_run_download, job.id, req)
    return EnqueueResponse(job_id=job.id)

@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str):
    job = store.get(job_id)
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
        result_path=str(job.result_path) if job.result_path else None,
    )

@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    async def eventgen():
        last = None
        while True:
            if await request.is_disconnected():
                break
            job = store.get(job_id)
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
                "result_path": str(job.result_path) if job.result_path else None,
            }
            # sende bei Änderung ~2/s
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if job.status in ("completed", "failed"):
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(eventgen(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
