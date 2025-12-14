from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlparse


def build_strm_content(url: str) -> str:
    """
    Build `.strm` file content.

    A `.strm` file is plain text with a single line containing a path/URL.
    For AniBridge we write one HTTP(S) URL per file (UTF-8, newline-terminated).
    """
    u = (url or "").strip()
    if not u:
        raise ValueError("STRM url is empty")
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"STRM url must be http(s), got scheme={parsed.scheme!r}")
    return u + "\n"


def sanitize_strm_basename(name: str) -> str:
    """
    Sanitize a user-facing release name into a filesystem-safe basename.

    Keeps the result reasonably readable for media servers while preventing
    directory traversal and illegal filename characters.
    """
    base = (name or "").strip()
    if not base:
        base = "Episode"

    # Avoid names that media servers may treat as extras/samples.
    base = re.sub(r"(?i)\bsample\b", "clip", base)

    # Replace path separators and other illegal characters.
    base = re.sub(r'[\\/:*?"<>|]+', "_", base)

    # Collapse whitespace/underscores.
    base = re.sub(r"[\s_]+", " ", base).strip()

    # Don't allow empty/hidden basenames.
    if not base or base in (".", ".."):
        base = "Episode"
    if base.startswith("."):
        base = base.lstrip(".") or "Episode"
    return base


def allocate_unique_strm_path(dest_dir: Path, base_name: str) -> Path:
    """
    Allocate a unique `.strm` path under `dest_dir` by appending a numeric suffix.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = sanitize_strm_basename(base_name)
    candidate = dest_dir / f"{base}.strm"
    if not candidate.exists():
        return candidate

    i = 2
    while True:
        candidate = dest_dir / f"{base}.{i}.strm"
        if not candidate.exists():
            return candidate
        i += 1

