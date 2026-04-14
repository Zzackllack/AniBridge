from __future__ import annotations
from typing import Optional, Dict, Any, List, cast
import warnings
from loguru import logger
import yt_dlp

from app.core.downloader import get_direct_url_with_fallback, build_episode
from app.utils.naming import quality_from_info
from app.config import PROVIDER_ORDER, CATALOG_SITE_CONFIGS
from app.utils.logger import config as configure_logger
from app.providers.megakino.client import get_default_client

configure_logger()


def probe_episode_quality_once(
    direct_url: str, timeout: float = 6.0
) -> tuple[Optional[int], Optional[str], Dict[str, Any] | None]:
    """
    Retrieve reported video height, video codec, and metadata from a direct media URL without downloading the media.

    Parameters:
        timeout (float): Socket timeout in seconds used when probing the URL.

    Returns:
        tuple: A three-item tuple (height, vcodec, info_dict) where `height` is the reported video height in pixels or `None` if unavailable, `vcodec` is the reported video codec string or `None` if unavailable, and `info_dict` is the extracted metadata dictionary from yt-dlp or `None` if extraction failed.
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
        with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
            info = ydl.extract_info(direct_url, download=False)
            logger.debug(f"yt_dlp.extract_info returned: {info}")
        if not info:
            logger.warning("No info extracted from the URL.")
            return (None, None, None)
        # yt_dlp returns a specialized _InfoDict; cast to plain Dict for type checkers
        info_dict = cast(Dict[str, Any], info)
        h, vc = quality_from_info(info_dict)
        logger.info(f"Extracted quality: height={h}, vcodec={vc}")
        return (h, vc, info_dict)
    except Exception as e:
        logger.warning(f"Preflight probe failed for URL {direct_url}: {e}")
        return (None, None, None)


def probe_episode_quality(
    *,
    slug: str,
    season: int,
    episode: int,
    language: str,
    preferred_host: Optional[str] = None,
    preferred_provider: Optional[str] = None,
    timeout: float = 6.0,
    site: str = "aniworld.to",
) -> tuple[bool, Optional[int], Optional[str], Optional[str], Dict[str, Any] | None]:
    """
    Probe whether an episode is available in the requested language and return the host used along with reported video quality.

    Parameters:
        slug (str): Episode identifier (series slug).
        season (int): Season number.
        episode (int): Episode number.
        language (str): Desired audio/subtitle language code.
        preferred_host (Optional[str]): Video host to try first, if any.
        preferred_provider (Optional[str]): Deprecated alias for `preferred_host`.
        timeout (float): Socket/metadata probe timeout in seconds.
        site (str): Site identifier used when building the episode object.

    Returns:
        tuple[bool, Optional[int], Optional[str], Optional[str], Dict[str, Any] | None]:
            - available (bool): True if a host yielded playable metadata for the requested language, False otherwise.
            - height (Optional[int]): Reported video height in pixels, or None if unavailable.
            - vcodec (Optional[str]): Reported video codec string, or None if unavailable.
            - host_used (Optional[str]): Name of the video host that succeeded, or None if none succeeded.
            - raw_info (Dict[str, Any] | None): Raw metadata returned by the probe, or None if unavailable.
    """
    if preferred_host is None and preferred_provider is not None:
        warnings.warn(
            "preferred_provider is deprecated; use preferred_host instead",
            DeprecationWarning,
            stacklevel=2,
        )
        preferred_host = preferred_provider

    logger.info(
        f"Probing episode quality for slug={slug}, season={season}, episode={episode}, language={language}, "
        f"preferred_host={preferred_host}, timeout={timeout}, site={site}"
    )
    if "megakino" in site:
        try:
            client = get_default_client()
            direct, provider_used = client.resolve_direct_url(
                slug=slug, preferred_host=preferred_host
            )
        except Exception as exc:
            logger.warning(
                "Megakino direct URL resolution failed ({}): {}",
                type(exc).__name__,
                exc,
            )
            return (False, None, None, None, None)
        logger.debug(
            "Megakino direct URL resolved: provider={} url={}",
            provider_used,
            direct,
        )
        h, vc, info = probe_episode_quality_once(direct, timeout=timeout)
        available = True
        return (available, h, vc, provider_used, info)

    if site not in CATALOG_SITE_CONFIGS:
        logger.warning(f"Unknown site '{site}', defaulting to aniworld.to")
        site = "aniworld.to"
    ep = build_episode(slug=slug, season=season, episode=episode, site=site)
    logger.debug(f"Built episode object: {ep}")
    candidates: List[str] = []
    if preferred_host:
        candidates.append(preferred_host)
        logger.debug(f"Preferred host added: {preferred_host}")
    for p in PROVIDER_ORDER:
        if p not in candidates:
            candidates.append(p)
    logger.debug(f"Host candidates: {candidates}")
    for prov in candidates:
        logger.info(f"Trying host: {prov}")
        try:
            direct, chosen = get_direct_url_with_fallback(
                ep, preferred=prov, language=language
            )
            logger.debug(f"Got direct URL: {direct} (chosen host: {chosen})")
            h, vc, info = probe_episode_quality_once(direct, timeout=timeout)
            logger.info(
                f"Host '{chosen}' succeeded: available=True, height={h}, vcodec={vc}"
            )
            return (True, h, vc, chosen, info)
        except Exception as e:
            logger.warning(
                "Host '{}' failed ({}): {}",
                prov,
                type(e).__name__,
                e,
            )
            continue
    logger.error("No host succeeded for this episode/language.")
    return (False, None, None, None, None)
