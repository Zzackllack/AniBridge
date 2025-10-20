from __future__ import annotations
from typing import Optional, Tuple, Dict, Any, List
from loguru import logger
import yt_dlp
import os
import sys

from app.core.downloader import get_direct_url_with_fallback, build_episode
from app.utils.naming import quality_from_info
from app.config import PROVIDER_ORDER
from app.utils.logger import config as configure_logger
from app.infrastructure.network import yt_dlp_proxy

configure_logger()


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
        proxy_url = yt_dlp_proxy()
        if proxy_url:
            ydl_opts["proxy"] = proxy_url
            logger.debug(f"yt-dlp probe proxy enabled: {proxy_url}")
    except Exception as e:
        logger.debug(f"yt-dlp probe proxy configuration failed: {e}")
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
    site: str = "aniworld.to",
) -> tuple[bool, Optional[int], Optional[str], Optional[str], Dict[str, Any] | None]:
    """
    Probe whether an episode is available in the requested language and return the provider used along with reported video quality.

    Parameters:
        slug (str): Episode identifier (series slug).
        season (int): Season number.
        episode (int): Episode number.
        language (str): Desired audio/subtitle language code.
        preferred_provider (Optional[str]): Provider to try first, if any.
        timeout (float): Socket/metadata probe timeout in seconds.
        site (str): Site identifier used when building the episode object.

    Returns:
        tuple[bool, Optional[int], Optional[str], Optional[str], Dict[str, Any] | None]:
            - available (bool): True if a provider yielded playable metadata for the requested language, False otherwise.
            - height (Optional[int]): Reported video height in pixels, or None if unavailable.
            - vcodec (Optional[str]): Reported video codec string, or None if unavailable.
            - provider_used (Optional[str]): Name of the provider that succeeded, or None if none succeeded.
            - raw_info (Dict[str, Any] | None): Raw metadata returned by the probe, or None if unavailable.
    """
    logger.info(
        f"Probing episode quality for slug={slug}, season={season}, episode={episode}, language={language}, "
        f"preferred_provider={preferred_provider}, timeout={timeout}, site={site}"
    )
    ep = build_episode(slug=slug, season=season, episode=episode, site=site)
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
