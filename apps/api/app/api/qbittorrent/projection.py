"""Shared projection of untouched legacy jobs in both qBittorrent modes."""

import os
from types import SimpleNamespace

from loguru import logger

from app.config import DOWNLOAD_DIR, QBIT_PUBLIC_SAVE_PATH
from app.catalog.output_state import missing_output
from app.db import ClientTask, Job


def torrent_info_record(
    r: ClientTask | SimpleNamespace, job: Job | SimpleNamespace | None
) -> dict[str, object]:
    """Keep the released fields for legacy records without changing their state."""
    state = r.state
    progress = 0.0
    dlspeed = 0
    eta = 0
    size = job.total_bytes if job and job.total_bytes else 0
    missing = False
    if job:
        missing = missing_output(
            {
                key: getattr(job, key, None)
                for key in ("status", "progress", "message", "result_path")
            }
        )
        progress = (job.progress or 0.0) / 100.0
        dlspeed = int(job.speed or 0)
        eta = int(job.eta or 0)
        if job.status == "completed":
            state = "uploading"
            dlspeed = 0
            if job.result_path and os.path.exists(job.result_path):
                try:
                    size = int(os.path.getsize(job.result_path))
                except Exception:
                    pass
        elif job.status == "failed":
            state = "error"
        elif job.status == "cancelled":
            state = "pausedDL"
        else:
            state = "downloading"
        if missing:
            state, progress, dlspeed = "missingFiles", 1.0, 0
        logger.trace(
            "Job {}: status={}, wire_state={}, progress={}, speed={}, eta={}",
            job.id,
            job.status,
            state,
            progress,
            dlspeed,
            eta,
        )

    content_path = None
    save_path_val = r.save_path or (QBIT_PUBLIC_SAVE_PATH or str(DOWNLOAD_DIR))
    if job and job.result_path and not missing:
        try:
            content_abs = os.path.abspath(job.result_path)
            if QBIT_PUBLIC_SAVE_PATH:
                content_path = os.path.join(
                    QBIT_PUBLIC_SAVE_PATH, os.path.basename(content_abs)
                )
                save_path_val = QBIT_PUBLIC_SAVE_PATH
            else:
                content_path = content_abs
                save_path_val = os.path.abspath(os.path.dirname(content_abs))
        except Exception:
            content_path = job.result_path

    return {
        "hash": r.hash,
        "name": r.name,
        "state": state,
        "progress": progress,
        "dlspeed": dlspeed,
        "upspeed": 0,
        "eta": eta,
        "category": r.category or "",
        "save_path": save_path_val,
        "content_path": content_path or "",
        "added_on": int(r.added_on.timestamp()),
        "completion_on": int((r.completion_on or r.added_on).timestamp()),
        "size": int(size or 0),
        "num_seeds": 0,
        "num_leechs": 0,
        "anibridge_output_missing": missing,
    }
