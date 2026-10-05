"""Stable local output ownership shared by execution and retention."""

import re
from pathlib import Path


def output_paths(payload: dict, job_id: str) -> tuple[Path, Path]:
    label = (
        re.sub(r"[^\w. -]", "_", payload["original_label"])[:160].strip(" .")
        or "AniBridge"
    )
    root = Path(payload["save_path"]).resolve() / f"{label}.{job_id}"
    suffix = "strm" if payload.get("mode") == "strm" else "mkv"
    return root, root / f"{label}.{suffix}"
