from __future__ import annotations
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Tuple, Optional
from loguru import logger
from sqlmodel import Session
import errno

from app.config import MAX_CONCURRENCY, DOWNLOAD_DIR
from app.utils.strm import allocate_unique_strm_path, build_strm_content
from app.utils.terminal import (
    ProgressReporter,
    ProgressSnapshot,
    is_interactive_terminal,
)
from app.db import engine, create_job, update_job
from app.core.downloader import (
    download_episode,
    Provider,
    Language,
    build_episode,
    get_direct_url_with_fallback,
)
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
    Run a download task and record its progress and final state in the database.

    Executes the episode download described by `req`, updates the job row with lifecycle states
    (e.g., "downloading", "completed", "failed", "cancelled"), writes final `result_path` on success,
    and removes the job from the in-memory RUNNING registry when finished. If the download is cancelled
    or an exception occurs, the job status and message are updated accordingly. An OSError caused by
    an unwritable download directory sets the job to "failed" with a directory-specific message.

    Parameters:
        job_id (str): Identifier of the job being run.
        req (dict): Download request with keys used by the downloader. Recognized keys:
            - 'slug', 'season', 'episode' (episode identifiers)
            - 'language' (optional)
            - 'provider' (optional)
            - 'title_hint' (optional)
            - 'link' (optional)
            - 'site' (optional, defaults to "aniworld.to")
        stop_event (threading.Event): Event that, when set, requests cancellation of the download.
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


def _run_strm(job_id: str, req: dict, stop_event: threading.Event) -> None:
    """
    Create a `.strm` file pointing to a resolved remote media URL.

    The URL is resolved via the AniWorld library using the same provider fallback
    strategy as downloads, but instead of downloading bytes, we write a small
    `.strm` file to `DOWNLOAD_DIR`.
    """
    try:
        with Session(engine) as s:
            site = req.get("site", "aniworld.to")
            update_job(s, job_id, status="downloading", message=None, source_site=site)

        if stop_event.is_set():
            raise Exception("Cancelled")

        site = str(req.get("site") or "aniworld.to")
        ep = build_episode(
            slug=req.get("slug"),
            season=req.get("season"),
            episode=req.get("episode"),
            site=site,
        )
        direct_url, provider_used = get_direct_url_with_fallback(
            ep, preferred=req.get("provider"), language=str(req.get("language") or "")
        )

        if stop_event.is_set():
            raise Exception("Cancelled")

        title_hint = str(req.get("title_hint") or "").strip()
        if title_hint:
            base_name = title_hint
        else:
            slug = str(req.get("slug") or "Episode")
            try:
                s_i = int(req.get("season"))
                e_i = int(req.get("episode"))
                base_name = f"{slug}.S{s_i:02d}E{e_i:02d}"
            except Exception:
                base_name = slug
        out_path = allocate_unique_strm_path(DOWNLOAD_DIR, base_name)
        content = build_strm_content(direct_url)
        tmp_path = out_path.with_suffix(".strm.tmp")
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        tmp_path.replace(out_path)

        with Session(engine) as s:
            update_job(
                s,
                job_id,
                status="completed",
                progress=100.0,
                downloaded_bytes=len(content.encode("utf-8")),
                total_bytes=len(content.encode("utf-8")),
                result_path=str(out_path),
                message=f"STRM created (provider={provider_used})",
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
    Schedule a background download job and return its job identifier.

    Parameters:
        req (dict): Download request containing:
            - slug (str): Content identifier.
            - season (int | str): Season number or identifier.
            - episode (int | str): Episode number or identifier.
            - language (str): Desired audio/subtitle language.
            - provider (str, optional): Provider to use.
            - title_hint (str, optional): Suggested title for the download destination.
            - link (str, optional): Direct link or reference.
            - site (str, optional): Source site name; used as the job's source_site (defaults to "aniworld.to").

    Returns:
        str: The created job's identifier.

    Raises:
        RuntimeError: If the thread pool executor is unavailable after initialization.
    """
    init_executor()
    if EXECUTOR is None:
        raise RuntimeError("executor not available")

    with Session(engine) as s:
        job = create_job(s, source_site=req.get("site") or "aniworld.to")

    stop_event = threading.Event()
    mode = str(req.get("mode") or "").strip().lower()
    runner = _run_strm if mode == "strm" else _run_download
    fut = EXECUTOR.submit(runner, job.id, req, stop_event)
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
