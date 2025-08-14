from __future__ import annotations
from typing import Optional, Tuple, Dict, Any, List
from loguru import logger
import yt_dlp

from app.downloader import get_direct_url_with_fallback, build_episode
from app.naming import quality_from_info
from app.config import PROVIDER_ORDER


def probe_episode_quality_once(
    direct_url: str, timeout: float = 6.0
) -> tuple[Optional[int], Optional[str], Dict[str, Any] | None]:
    """
    Lädt KEINE Daten. Holt nur Info über Formate/Höhe/Codec.
    """
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "noprogress": True,
        "socket_timeout": timeout,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(direct_url, download=False)
        if not info:
            return (None, None, None)
        h, vc = quality_from_info(info)
        return (h, vc, info)
    except Exception as e:
        logger.warning(f"Preflight probe failed: {e}")
        return (None, None, None)


def probe_episode_quality(
    *,
    slug: str,
    season: int,
    episode: int,
    language: str,
    preferred_provider: Optional[str] = None,
    timeout: float = 6.0,
) -> tuple[bool, Optional[int], Optional[str], Optional[str], Dict[str, Any] | None]:
    """
    Gibt zurück: (available, height, vcodec, provider_used, raw_info)
      - available=False, wenn kein Provider/Language funktioniert.
    """
    ep = build_episode(slug=slug, season=season, episode=episode)
    candidates: List[str] = []
    if preferred_provider:
        candidates.append(preferred_provider)
    for p in PROVIDER_ORDER:
        if p not in candidates:
            candidates.append(p)
    for prov in candidates:
        try:
            direct, chosen = get_direct_url_with_fallback(
                ep, preferred=prov, language=language
            )
            h, vc, info = probe_episode_quality_once(direct, timeout=timeout)
            return (True, h, vc, chosen, info)
        except Exception:
            continue
    return (False, None, None, None, None)
