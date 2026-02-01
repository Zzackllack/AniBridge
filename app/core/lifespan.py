from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional

from loguru import logger
from fastapi import FastAPI
from sqlmodel import Session

from app.infrastructure.network import (
    apply_global_proxy_env,
    log_proxy_config_summary,
    start_ip_check_thread,
)
from app.infrastructure.system_info import log_full_system_report
from app.utils.update_notifier import notify_on_startup
from app.utils.domain_resolver import (
    resolve_megakino_base_url,
    start_megakino_domain_check_thread,
)

from app.config import (
    DOWNLOAD_DIR,
    DOWNLOADS_TTL_HOURS,
    CLEANUP_SCAN_INTERVAL_MIN,
    CATALOG_SITE_CONFIGS,
    ANIBRIDGE_TEST_MODE,
)

from app.core.scheduler import init_executor, shutdown_executor
from app.db import (
    engine,
    dispose_engine,
    create_db_and_tables,
    cleanup_dangling_jobs,
)


def _start_ttl_cleanup_thread(
    stop_event: threading.Event,
) -> Optional[threading.Thread]:
    """Start a background thread that deletes old downloads based on TTL."""

    def _cleanup_loop():
        exts = {".mp4", ".mkv", ".webm", ".avi", ".m4v"}
        ttl = timedelta(hours=float(DOWNLOADS_TTL_HOURS))
        logger.info(
            f"Starting cleanup thread: dir={DOWNLOAD_DIR}, ttl={ttl}, interval={CLEANUP_SCAN_INTERVAL_MIN}min"
        )
        while not stop_event.wait(max(1, int(CLEANUP_SCAN_INTERVAL_MIN)) * 60):
            now = datetime.utcnow()
            try:
                for root, _, files in os.walk(DOWNLOAD_DIR):
                    for fname in files:
                        try:
                            if os.path.splitext(fname)[1].lower() not in exts:
                                continue
                            fpath = os.path.join(root, fname)
                            st = os.stat(fpath)
                            mtime = datetime.utcfromtimestamp(st.st_mtime)
                            if now - mtime >= ttl:
                                try:
                                    os.remove(fpath)
                                    logger.success(f"TTL cleanup: deleted {fpath}")
                                except Exception as e:
                                    logger.warning(
                                        f"TTL cleanup: failed to delete {fpath}: {e}"
                                    )
                        except FileNotFoundError:
                            continue
                        except Exception as e:
                            logger.warning(f"TTL cleanup: error on file {fname}: {e}")
                # Try removing empty leaf dirs under DOWNLOAD_DIR
                for root, dirs, files in os.walk(DOWNLOAD_DIR, topdown=False):
                    try:
                        if not dirs and not files and root != str(DOWNLOAD_DIR):
                            os.rmdir(root)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"TTL cleanup loop error: {e}")

    if DOWNLOADS_TTL_HOURS <= 0:
        logger.info("Downloads TTL cleanup disabled (DOWNLOADS_TTL_HOURS<=0)")
        return None
    t = threading.Thread(target=_cleanup_loop, name="cleanup", daemon=True)
    t.start()
    return t


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply proxy env before any outbound network calls (e.g., update check)
    """
    Manage application startup and shutdown tasks for the given FastAPI application.

    On startup this function performs best-effort initialization: applies global proxy settings, logs proxy and system reports, sends a startup notification, creates the database and tables, resets dangling jobs, initializes the executor, resolves Megakino domain configuration when present, and starts background worker threads (TTL cleanup, IP check, and optional Megakino domain checker).

    On shutdown it gracefully stops the executor, disposes the DB engine, and signals background threads to stop by setting their respective stop events.

    Parameters:
        app (FastAPI): The FastAPI application instance whose lifespan is being managed.
    """
    try:
        apply_global_proxy_env()
    except Exception as e:
        logger.warning(f"apply_global_proxy_env failed: {e}")
    try:
        log_proxy_config_summary()
    except Exception as e:
        logger.warning(f"log_proxy_config_summary failed: {e}")

    # System report and update notifier (best effort)
    if not ANIBRIDGE_TEST_MODE:
        try:
            log_full_system_report()
        except Exception as e:
            logger.warning(f"log_full_system_report failed: {e}")

        try:
            notify_on_startup()
        except Exception as e:
            logger.warning(f"notify_on_startup failed: {e}")
    logger.info("Application startup: creating DB and thread pool executor.")
    create_db_and_tables()
    with Session(engine) as s:
        cleaned = cleanup_dangling_jobs(s)
        if cleaned:
            logger.warning(f"Reset {cleaned} dangling jobs to 'failed'")
    init_executor()

    # Start background workers
    cleanup_stop = threading.Event()
    ip_stop = threading.Event()
    megakino_stop = threading.Event()
    if "megakino" in CATALOG_SITE_CONFIGS and not ANIBRIDGE_TEST_MODE:
        try:
            resolve_megakino_base_url()
        except Exception as e:
            logger.warning(f"megakino domain resolution failed: {e}")
    try:
        _start_ttl_cleanup_thread(cleanup_stop)
    except Exception as e:
        logger.debug(f"cleanup thread start failed: {e}")
    try:
        if not ANIBRIDGE_TEST_MODE:
            start_ip_check_thread(ip_stop)
    except Exception as e:
        logger.debug(f"start_ip_check_thread failed: {e}")
    if "megakino" in CATALOG_SITE_CONFIGS and not ANIBRIDGE_TEST_MODE:
        try:
            start_megakino_domain_check_thread(megakino_stop)
        except Exception as e:
            logger.debug(f"start_megakino_domain_check_thread failed: {e}")

    try:
        yield
    finally:
        # Shutdown services
        shutdown_executor()
        try:
            dispose_engine()
        except Exception as e:
            logger.warning("dispose_engine failed: {}", e)
        try:
            cleanup_stop.set()
        except Exception as e:
            logger.warning("cleanup_stop.set failed: {}", e)
        try:
            ip_stop.set()
        except Exception as e:
            logger.warning("ip_stop.set failed: {}", e)
        try:
            megakino_stop.set()
        except Exception as e:
            logger.warning("megakino_stop.set failed: {}", e)
