from __future__ import annotations
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Tuple, Optional
from loguru import logger
from sqlmodel import Session
import errno

from app.config import MAX_CONCURRENCY, DOWNLOAD_DIR
from app.models import engine, create_job, update_job
from app.core.downloader import download_episode, Provider, Language
from app.utils.logger import config as configure_logger

configure_logger()

# global executor + registry
EXECUTOR: Optional[ThreadPoolExecutor] = None
RUNNING: Dict[str, Tuple[Future, threading.Event]] = {}
RUNNING_LOCK = threading.Lock()


def init_executor() -> None:
    global EXECUTOR
    if EXECUTOR is None:
        EXECUTOR = ThreadPoolExecutor(
            max_workers=MAX_CONCURRENCY, thread_name_prefix="anibridge"
        )
        logger.info(f"Scheduler: executor started with max_workers={MAX_CONCURRENCY}")


def shutdown_executor() -> None:
    global EXECUTOR
    with RUNNING_LOCK:
        for _, (_, ev) in list(RUNNING.items()):
            ev.set()
        RUNNING.clear()
    if EXECUTOR:
        EXECUTOR.shutdown(wait=False, cancel_futures=True)
        logger.info("Scheduler: executor shutdown requested")
    EXECUTOR = None


def _progress_updater(job_id: str, stop_event: threading.Event):
    from sqlmodel import Session
    from app.models import engine, update_job

    def _cb(d: dict):
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
        with Session(engine) as s:
            update_job(
                s,
                job_id,
                status="downloading" if status != "finished" else "downloading",
                downloaded_bytes=downloaded,
                total_bytes=int(total) if total else None,
                speed=float(speed) if speed else None,
                eta=int(eta) if eta else None,
                progress=progress,
            )

    return _cb


def _run_download(job_id: str, req: dict, stop_event: threading.Event):
    try:
        with Session(engine) as s:
            update_job(s, job_id, status="downloading", message=None)

        dest = download_episode(
            link=req.get("link"),
            slug=req.get("slug"),
            season=req.get("season"),
            episode=req.get("episode"),
            provider=req.get("provider"),
            language=(
                str(req.get("language")) if req.get("language") is not None else ""
            ),
            dest_dir=DOWNLOAD_DIR,
            title_hint=req.get("title_hint"),
            progress_cb=_progress_updater(job_id, stop_event),
            stop_event=stop_event,
        )

        with Session(engine) as s:
            update_job(
                s, job_id, status="completed", progress=100.0, result_path=str(dest)
            )
    except OSError as e:
        with Session(engine) as s:
            if e.errno in (errno.EACCES, errno.EROFS):
                update_job(
                    s,
                    job_id,
                    status="failed",
                    message=f"Download dir not writable: {e}",
                )
            else:
                update_job(s, job_id, status="failed", message=str(e))
    except Exception as e:
        msg = str(e)
        status = "failed"
        if "Cancel" in msg or "cancel" in msg:
            status = "cancelled"
            msg = "Cancelled by user"
        with Session(engine) as s:
            update_job(s, job_id, status=status, message=msg)
    finally:
        with RUNNING_LOCK:
            RUNNING.pop(job_id, None)


def schedule_download(req: dict) -> str:
    """
    req: {slug, season, episode, language, provider?, title_hint?, link?}
    returns job_id
    """
    init_executor()
    if EXECUTOR is None:
        raise RuntimeError("executor not available")

    with Session(engine) as s:
        job = create_job(s)

    stop_event = threading.Event()
    fut = EXECUTOR.submit(_run_download, job.id, req, stop_event)
    with RUNNING_LOCK:
        RUNNING[job.id] = (fut, stop_event)
    return job.id


def cancel_job(job_id: str) -> None:
    with RUNNING_LOCK:
        item = RUNNING.get(job_id)
    if not item:
        return
    fut, ev = item
    ev.set()
    fut.cancel()
