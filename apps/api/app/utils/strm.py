from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlparse


def build_strm_content(url: str) -> str:
    """
    Create .strm file content containing a single HTTP(S) URL followed by a newline.

    The input URL is validated to be non-empty and to use the http or https scheme.

    Parameters:
        url (str): Direct HTTP(S) URL to embed in the .strm content.

    Returns:
        str: The validated URL ending with a single newline.

    Raises:
        ValueError: If the URL is empty or its scheme is not http or https.
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
    Produce a filesystem-safe basename from a user-facing release name.

    Performs human-readable normalization suitable for media servers: empty input becomes "Episode", the standalone word "sample" (case-insensitive) is replaced with "clip", path separators and characters illegal in filenames are replaced with underscores, runs of whitespace/underscores are collapsed to single spaces, and leading dots or reserved names (".", "..") are removed or replaced with "Episode".

    Parameters:
        name (str): Raw title or display name.

    Returns:
        str: Sanitized basename without the `.strm` extension.
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

    Parameters:
        dest_dir (Path): Directory to create the `.strm` file in.
        base_name (str): Raw display name used to build the filename.

    Returns:
        Path: A non-existing `.strm` path under `dest_dir`.
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
