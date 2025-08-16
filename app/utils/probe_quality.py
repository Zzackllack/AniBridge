from __future__ import annotations
from typing import Optional, Tuple, Dict, Any, List
from loguru import logger
import yt_dlp
import os
import sys

from app.downloader import get_direct_url_with_fallback, build_episode
from app.naming import quality_from_info
from app.config import PROVIDER_ORDER

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)


def probe_episode_quality_once(
    direct_url: str, timeout: float = 6.0
) -> tuple[Optional[int], Optional[str], Dict[str, Any] | None]:
    """
    Lädt KEINE Daten. Holt nur Info über Formate/Höhe/Codec.
    """
    logger.debug(
        f"Probing episode quality for URL: {direct_url} with timeout={timeout}"
    )
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "noprogress": True,
        "socket_timeout": timeout,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(direct_url, download=False)
            logger.debug(f"yt_dlp.extract_info returned: {info}")
        if not info:
            logger.warning("No info extracted from the URL.")
            return (None, None, None)
        h, vc = quality_from_info(info)
        logger.info(f"Extracted quality: height={h}, vcodec={vc}")
        return (h, vc, info)
    except Exception as e:
        logger.warning(f"Preflight probe failed for URL {direct_url}: {e}")
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
    logger.info(
        f"Probing episode quality for slug={slug}, season={season}, episode={episode}, language={language}, "
        f"preferred_provider={preferred_provider}, timeout={timeout}"
    )
    ep = build_episode(slug=slug, season=season, episode=episode)
    logger.debug(f"Built episode object: {ep}")
    candidates: List[str] = []
    if preferred_provider:
        candidates.append(preferred_provider)
        logger.debug(f"Preferred provider added: {preferred_provider}")
    for p in PROVIDER_ORDER:
        if p not in candidates:
            candidates.append(p)
    logger.debug(f"Provider candidates: {candidates}")
    for prov in candidates:
        logger.info(f"Trying provider: {prov}")
        try:
            direct, chosen = get_direct_url_with_fallback(
                ep, preferred=prov, language=language
            )
            logger.debug(f"Got direct URL: {direct} (chosen provider: {chosen})")
            h, vc, info = probe_episode_quality_once(direct, timeout=timeout)
            logger.info(
                f"Provider '{chosen}' succeeded: available=True, height={h}, vcodec={vc}"
            )
            return (True, h, vc, chosen, info)
        except Exception as e:
            logger.warning(f"Provider '{prov}' failed: {e}")
            continue
    logger.error("No provider succeeded for this episode/language.")
    return (False, None, None, None, None)

