from __future__ import annotations

import asyncio
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.scheduler import schedule_download, RUNNING, RUNNING_LOCK
from app.models import get_session, get_job as db_get_job

from app.core.downloader import Provider, Language


router = APIRouter()


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


@router.post("/downloader/download", response_model=EnqueueResponse)
def enqueue_download(req: DownloadRequest, session: Session = Depends(get_session)):
    job_id = schedule_download(req.model_dump())
    return EnqueueResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
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


@router.get("/jobs/{job_id}/events")
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


@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    with RUNNING_LOCK:
        item = RUNNING.get(job_id)
    if not item:
        return {"status": "not-running"}
    fut, ev = item
    ev.set()
    fut.cancel()
    return {"status": "cancelling"}

