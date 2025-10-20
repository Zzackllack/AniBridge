from __future__ import annotations
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Tuple, Optional
from loguru import logger
from sqlmodel import Session
import errno

from app.config import MAX_CONCURRENCY, DOWNLOAD_DIR
from app.utils.terminal import (
    ProgressReporter,
    ProgressSnapshot,
    is_interactive_terminal,
)
from app.db import engine, create_job, update_job
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
    from app.db import engine, update_job

    reporter: ProgressReporter | None = None
    last_db_n = -1

    def _cb(d: dict):
        nonlocal reporter, last_db_n
        if stop_event.is_set():
            if reporter:
                reporter.close()
            raise Exception("Cancelled")

        status = d.get("status")
        downloaded = int(d.get("downloaded_bytes") or 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        speed = d.get("speed")
        eta = d.get("eta")

        # Initialize reporter lazily (label contains job id)
        if reporter is None:
            reporter = ProgressReporter(label=f"Job {job_id}")

        # Render progress to terminal (TTY bar or stepped logs)
        reporter.update(
            ProgressSnapshot(
                downloaded=downloaded,
                total=int(total) if total else None,
                speed=float(speed) if speed else None,
                eta=int(eta) if eta else None,
                status=str(status) if status else None,
            )
        )

        # Throttle DB writes to ~1% steps (or on finish)
        progress = 0.0
        should_write = True
        if total:
            try:
                total_i = int(total)
                step = max(1, total_i // 100)
                should_write = downloaded == total_i or downloaded // step != last_db_n
                last_db_n = downloaded // step
                progress = max(0.0, min(100.0, downloaded / total_i * 100.0))
            except Exception:
                should_write = True

        if should_write:
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

        if status == "finished" and reporter is not None:
            reporter.close()

    return _cb


def _run_download(job_id: str, req: dict, stop_event: threading.Event):
    """
    Execute a download job: start the episode download, update the job record in the database with progress/result, and handle errors or cancellation.
    
    Parameters:
        job_id (str): Identifier of the job being run.
        req (dict): Download request containing keys used by the downloader:
            - 'slug', 'season', 'episode' (identifiers for the episode)
            - 'language' (optional)
            - 'provider' (optional)
            - 'title_hint' (optional)
            - 'link' (optional)
            - 'site' (optional, defaults to "aniworld.to")
        stop_event (threading.Event): Event that, when set, requests cancellation of the download.
    
    Side effects:
        - Updates the job row in the database with status, progress, messages, source site, and result path.
        - Removes the job from the RUNNING registry when finished.
    """
    try:
        with Session(engine) as s:
            site = req.get("site", "aniworld.to")
            update_job(s, job_id, status="downloading", message=None, source_site=site)

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
            site=req.get("site", "aniworld.to"),
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