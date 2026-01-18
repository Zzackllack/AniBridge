import os
import socket
from typing import Optional, Tuple

from app.utils.http_client import get as http_get
from loguru import logger
from packaging import version as _version

from app._version import get_version
from app.config import IN_DOCKER

GITHUB_OWNER = os.getenv("ANIBRIDGE_GITHUB_OWNER", "zzackllack").strip()
GITHUB_REPO = os.getenv("ANIBRIDGE_GITHUB_REPO", "AniBridge").strip()
GHCR_IMAGE = os.getenv("ANIBRIDGE_GHCR_IMAGE", "zzackllack/anibridge").strip()


def _normalize(ver: str) -> str:
    v = ver.strip()
    if v.lower().startswith("v"):
        v = v[1:]
    return v


def _compare_versions(current: str, latest: str) -> int:
    """Compare semantic versions. Returns -1, 0, 1 for current < = > latest.

    Falls back to string compare if parsing fails.
    """
    try:
        c = _version.parse(_normalize(current))
        l = _version.parse(_normalize(latest))
        if c < l:
            return -1
        if c > l:
            return 1
        return 0
    except Exception:
        # Fallback: basic compare as strings (not ideal, but safe)
        return (current > latest) - (current < latest)


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN") or os.getenv("ANIBRIDGE_GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_latest_github_release(owner: str, repo: str) -> Optional[str]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        resp = http_get(url, headers=_github_headers(), timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            tag = data.get("tag_name") or data.get("name")
            if tag:
                return _normalize(str(tag))
            # Fallback: if no releases, try tags endpoint
        else:
            # If repo has no releases, GitHub may return 404; fallback to tags
            logger.debug(f"GitHub releases response: {resp.status_code}")
    except Exception as e:
        logger.debug(f"GitHub releases fetch failed: {e}")

    # Fallback to tags API (first tag assumed latest by API ordering is not guaranteed)
    try:
        tags_url = f"https://api.github.com/repos/{owner}/{repo}/tags"
        resp = http_get(tags_url, headers=_github_headers(), timeout=5)
        if resp.status_code == 200:
            arr = resp.json()
            if isinstance(arr, list) and arr:
                tag = arr[0].get("name")
                if tag:
                    return _normalize(str(tag))
    except Exception as e:
        logger.debug(f"GitHub tags fetch failed: {e}")

    return None


def try_fetch_latest_ghcr_tag(image: str) -> Optional[str]:
    """Attempt to fetch the latest available tag for a GHCR image.

    Public GHCR tag listing sometimes requires auth; we attempt unauthenticated
    discovery and fall back to GitHub releases if not available.
    """
    # Docker Registry v2 tags list endpoint
    url = f"https://ghcr.io/v2/{image}/tags/list"
    try:
        resp = http_get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            tags = data.get("tags") or []
            # Prefer semver-looking tags, then 'latest'
            semver_tags = [t for t in tags if any(ch.isdigit() for ch in t)]
            candidates = semver_tags or tags
            if not candidates:
                return None
            # Heuristic: sort semver-ish descending using packaging, else lexicographic
            try:
                candidates_sorted = sorted(
                    candidates,
                    key=lambda t: _version.parse(_normalize(t)),
                    reverse=True,
                )
            except Exception:
                candidates_sorted = sorted(candidates, reverse=True)
            # Skip non-version aliases like 'latest' if there are proper tags
            for t in candidates_sorted:
                if t == "latest":
                    continue
                return _normalize(t)
            return _normalize(candidates_sorted[0])
        else:
            logger.debug(f"GHCR tags list status: {resp.status_code}")
    except Exception as e:
        logger.debug(f"GHCR tags fetch failed: {e}")

    return None


def check_for_update() -> Tuple[str, Optional[str]]:
    """Return tuple of (current_version, latest_version or None).

    Does not raise; logs internal errors at debug level only.
    """
    current = get_version()
    latest: Optional[str] = None

    # Prefer GHCR when running in Docker; fall back to GitHub
    if IN_DOCKER:
        latest = try_fetch_latest_ghcr_tag(GHCR_IMAGE)
        if not latest:
            latest = fetch_latest_github_release(GITHUB_OWNER, GITHUB_REPO)
    else:
        latest = fetch_latest_github_release(GITHUB_OWNER, GITHUB_REPO)

    return current, latest


def notify_on_startup() -> None:
    """Log current and latest version info, with a warning if an update exists."""
    # Allow opt-out via env
    flag = (os.getenv("ANIBRIDGE_UPDATE_CHECK", "1").strip().lower()) in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not flag:
        logger.info("Update check disabled via ANIBRIDGE_UPDATE_CHECK=0")
        return

    try:
        current, latest = check_for_update()
        if latest:
            cmp = _compare_versions(current, latest)
            logger.info(f"AniBridge version: current={current}, latest={latest}")
            if cmp < 0:
                if IN_DOCKER:
                    logger.warning(
                        "A new version is available. Update your container: "
                        f"ghcr.io/{GHCR_IMAGE}:v{latest}"
                    )
                else:
                    logger.warning(
                        f"A new version is available. Please update to v{latest}."
                    )
            elif cmp > 0:
                logger.info("You are running a newer (pre-release/dev) version.")
            else:
                logger.info("You are up-to-date.")
        else:
            # Could not determine latest version; keep this at INFO
            logger.info(f"AniBridge version: current={get_version()} (latest: unknown)")
    except Exception as e:
        # Never fail startup due to update check
        logger.debug(f"Update check failed: {e}")
