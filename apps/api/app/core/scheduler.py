from __future__ import annotations
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from loguru import logger
from sqlmodel import Session
import errno

from app.config import (
    DOWNLOAD_DIR,
    JOB_PROGRESS_FLUSH_SECONDS,
    MAX_CONCURRENCY,
    STRM_PROXY_MODE,
)
from app.utils.strm import allocate_unique_strm_path, build_strm_content
from app.core.strm_proxy import StrmIdentity, resolve_direct_url, build_stream_url
from app.utils.terminal import (
    ProgressReporter,
    ProgressSnapshot,
)
from app.db import engine, create_job, update_job, upsert_strm_mapping
from app.core.downloader import (
    download_episode,
)
from app.utils.logger import config as configure_logger

configure_logger()

# global executor + registry
EXECUTOR: Optional[ThreadPoolExecutor] = None
RUNNING: Dict[str, Tuple[Future | None, threading.Event]] = {}
RUNNING_LOCK = threading.Lock()


@dataclass(slots=True)
class JobProgressSnapshot:
    downloaded_bytes: int
    total_bytes: int | None
    speed: float | None
    eta: int | None
    progress: float


class JobProgressWriter:
    def __init__(self, job_id: str, flush_interval_seconds: float) -> None:
        self._job_id = job_id
        self._flush_interval_seconds = flush_interval_seconds
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._pending: JobProgressSnapshot | None = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"job-progress-writer-{job_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def publish(self, snapshot: JobProgressSnapshot) -> None:
        with self._lock:
            self._pending = snapshot
        self._wake_event.set()

    def close(self, *, flush: bool) -> None:
        self._stop_event.set()
        if not flush:
            with self._lock:
                self._pending = None
        self._wake_event.set()
        self._thread.join(timeout=5)

    def _drain_pending(self) -> JobProgressSnapshot | None:
        with self._lock:
            snapshot = self._pending
            self._pending = None
        return snapshot

    def _flush_snapshot(self, snapshot: JobProgressSnapshot) -> None:
        with Session(engine) as session:
            update_job(
                session,
                self._job_id,
                status="downloading",
                downloaded_bytes=snapshot.downloaded_bytes,
                total_bytes=snapshot.total_bytes,
                speed=snapshot.speed,
                eta=snapshot.eta,
                progress=snapshot.progress,
            )

    def _run(self) -> None:
        while True:
            self._wake_event.wait(self._flush_interval_seconds)
            self._wake_event.clear()
            snapshot = self._drain_pending()
            if snapshot is not None:
                self._flush_snapshot(snapshot)
            if self._stop_event.is_set():
                final_snapshot = self._drain_pending()
                if final_snapshot is not None:
                    self._flush_snapshot(final_snapshot)
                return


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
    reporter: ProgressReporter | None = None
    last_db_n = -1
    callback_lock = threading.Lock()
    writer = JobProgressWriter(
        job_id=job_id,
        flush_interval_seconds=JOB_PROGRESS_FLUSH_SECONDS,
    )
    writer.start()

    def _cb(d: dict):
        nonlocal reporter, last_db_n
        with callback_lock:
            if stop_event.is_set():
                if reporter:
                    reporter.close()
                raise Exception("Cancelled")

            status = d.get("status")
            downloaded = int(d.get("downloaded_bytes") or 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            speed = d.get("speed")
            eta = d.get("eta")
            total_i = int(total) if total else None
            speed_f = float(speed) if speed else None
            eta_i = int(eta) if eta else None

            if reporter is None:
                reporter = ProgressReporter(label=f"Job {job_id}")

            reporter.update(
                ProgressSnapshot(
                    downloaded=downloaded,
                    total=total_i,
                    speed=speed_f,
                    eta=eta_i,
                    status=str(status) if status else None,
                )
            )

            progress = 0.0
            should_write = True
            if total_i:
                try:
                    step = max(1, total_i // 100)
                    should_write = (
                        downloaded == total_i or downloaded // step != last_db_n
                    )
                    last_db_n = downloaded // step
                    progress = max(0.0, min(100.0, downloaded / total_i * 100.0))
                except Exception:
                    should_write = True

            if should_write:
                writer.publish(
                    JobProgressSnapshot(
                        downloaded_bytes=downloaded,
                        total_bytes=total_i,
                        speed=speed_f,
                        eta=eta_i,
                        progress=progress,
                    )
                )

            if status == "finished" and reporter is not None:
                reporter.close()

    return _cb, writer


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
    progress_cb, progress_writer = _progress_updater(job_id, stop_event)
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
            progress_cb=progress_cb,
            stop_event=stop_event,
            site=req.get("site", "aniworld.to"),
        )

        progress_writer.close(flush=True)
        with Session(engine) as s:
            update_job(
                s, job_id, status="completed", progress=100.0, result_path=str(dest)
            )
    except OSError as e:
        progress_writer.close(flush=False)
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
        progress_writer.close(flush=False)
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
    Create a .strm file in the configured download directory that points to a resolved remote media URL and update the job's status and result in the database.

    Parameters:
        job_id (str): Identifier of the job being executed; used to update job state.
        req (dict): STRM request containing identifiers and optional metadata. Recognized keys:
            - 'slug' (str)
            - 'season' (int)
            - 'episode' (int)
            - 'language' (str, optional)
            - 'provider' (str, optional)
            - 'title_hint' (str, optional) — preferred base filename for the .strm file
            - 'site' (str, optional) — source site, defaults to "aniworld.to"
            - 'mode' (str, optional)
        stop_event (threading.Event): Event that, when set, requests cancellation of the operation.

    Behavior:
        - Resolves a media URL for the requested episode, writes an atomic `.strm` file pointing to that URL, and marks the job as completed with the resulting path and progress.
        - If a proxy mode is enabled, records a mapping of the resolved URL and provider in the database and uses a proxied stream URL in the .strm.
        - On filesystem permission errors, marks the job as failed with a directory-related message; on cancellation marks the job as cancelled; on other errors marks the job as failed with the error message.
    """
    try:
        with Session(engine) as s:
            site = req.get("site", "aniworld.to")
            update_job(s, job_id, status="downloading", message=None, source_site=site)

        if stop_event.is_set():
            raise Exception("Cancelled")

        site = str(req.get("site") or "aniworld.to")
        season_raw = req.get("season")
        episode_raw = req.get("episode")
        if season_raw is None or episode_raw is None:
            raise ValueError("Missing season or episode for STRM request")
        try:
            season = int(season_raw)
            episode = int(episode_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid season or episode for STRM request") from exc
        identity = StrmIdentity(
            site=site,
            slug=str(req.get("slug") or ""),
            season=season,
            episode=episode,
            language=str(req.get("language") or ""),
            provider=str(req.get("provider") or "").strip() or None,
        )
        direct_url, provider_used = resolve_direct_url(identity)

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
        if STRM_PROXY_MODE == "proxy":
            strm_url = build_stream_url(identity)
            with Session(engine) as s:
                upsert_strm_mapping(
                    s,
                    site=identity.site,
                    slug=identity.slug,
                    season=identity.season,
                    episode=identity.episode,
                    language=identity.language,
                    provider=identity.provider,
                    resolved_url=direct_url,
                    provider_used=provider_used,
                    resolved_headers=None,
                )
        else:
            strm_url = direct_url
        content = build_strm_content(strm_url)
        content_bytes = content.encode("utf-8")
        tmp_path = out_path.with_suffix(".strm.tmp")
        # Write bytes to avoid platform newline translation.
        tmp_path.write_bytes(content_bytes)
        tmp_path.replace(out_path)

        with Session(engine) as s:
            update_job(
                s,
                job_id,
                status="completed",
                progress=100.0,
                downloaded_bytes=len(content_bytes),
                total_bytes=len(content_bytes),
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


def start_scheduled_job(job_id: str, req: dict) -> None:
    init_executor()
    if EXECUTOR is None:
        raise RuntimeError("executor not available")

    stop_event = threading.Event()
    mode = str(req.get("mode") or "").strip().lower()
    runner = _run_strm if mode == "strm" else _run_download
    with RUNNING_LOCK:
        if job_id in RUNNING:
            raise RuntimeError(f"job already running: {job_id}")
        RUNNING[job_id] = (None, stop_event)
    try:
        fut = EXECUTOR.submit(runner, job_id, req, stop_event)
    except Exception:
        with RUNNING_LOCK:
            current = RUNNING.get(job_id)
            if current is not None and current[1] is stop_event:
                RUNNING.pop(job_id, None)
        raise
    with RUNNING_LOCK:
        current = RUNNING.get(job_id)
        if current is None or current[1] is not stop_event:
            stop_event.set()
            fut.cancel()
            return
        RUNNING[job_id] = (fut, stop_event)


def create_scheduled_job(req: dict) -> str:
    with Session(engine) as s:
        job = create_job(s, source_site=req.get("site") or "aniworld.to")
    return job.id


def schedule_download(req: dict, *, autostart: bool = True) -> str:
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
    job_id = create_scheduled_job(req)
    if autostart:
        start_scheduled_job(job_id, req)
    return job_id


def cancel_job(job_id: str) -> None:
    with RUNNING_LOCK:
        item = RUNNING.get(job_id)
    if not item:
        return
    fut, ev = item
    ev.set()
    if fut is None:
        with RUNNING_LOCK:
            current = RUNNING.get(job_id)
            if current is not None and current[1] is ev and current[0] is None:
                RUNNING.pop(job_id, None)
        return
    fut.cancel()
