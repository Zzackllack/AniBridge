import os
import sys
from pathlib import Path
from typing import Optional, Literal, Callable, Tuple, Dict, Any, List
import re
import threading
import yt_dlp
from loguru import logger

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(sys.stdout, level=LOG_LEVEL, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

# Lib-API laut Doku:
# from aniworld.models import Anime, Episode
# -> get_direct_link(provider, language)
from aniworld.models import Anime, Episode  # type: ignore

from app.naming import rename_to_release
from app.config import PROVIDER_ORDER

Language = Literal["German Dub", "German Sub", "English Sub"]
Provider = Literal["VOE", "Vidoza", "Doodstream", "Filemoon", "Vidmoly", "Streamtape", "LoadX", "SpeedFiles", "Luluvdo"]
ProgressCb = Callable[[dict], None]  # bekommt yt-dlp progress dict

class DownloadError(Exception):
    pass

def _sanitize_filename(name: str) -> str:
    logger.debug(f"Sanitizing filename: {name}")
    sanitized = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    logger.debug(f"Sanitized filename: {sanitized}")
    return sanitized

def build_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None
) -> Episode:
    logger.info(f"Building episode: link={link}, slug={slug}, season={season}, episode={episode}")
    if link:
        logger.debug("Using direct link for episode.")
        return Episode(link=link)
    if slug and season and episode:
        logger.debug("Using slug/season/episode for episode.")
        return Episode(slug=slug, season=season, episode=episode)
    logger.error("Invalid episode parameters: must provide either link or (slug, season, episode).")
    raise ValueError("Provide either link OR (slug, season, episode).")

def _try_get_direct(ep: Episode, provider_name: str, language: Language) -> Optional[str]:
    logger.info(f"Trying provider '{provider_name}' for language '{language}'")
    try:
        url = ep.get_direct_link(provider_name, language)  # Lib-API
        if url:
            logger.success(f"Found direct URL from provider '{provider_name}': {url}")
            return url
        else:
            logger.warning(f"Provider '{provider_name}' returned no URL.")
    except Exception as e:
        logger.warning(f"Exception from provider '{provider_name}': {e}")
    return None

def get_direct_url_with_fallback(
    ep: Episode,
    *,
    preferred: Optional[str],
    language: Language,
) -> Tuple[str, str]:
    logger.info(f"Getting direct URL with fallback. Preferred: {preferred}, Language: {language}")
    tried: List[str] = []

    # preferred zuerst (wenn gesetzt)
    if preferred:
        p = preferred.strip()
        if p:
            tried.append(p)
            url = _try_get_direct(ep, p, language)
            if url:
                logger.success(f"Using preferred provider '{p}'")
                return url, p

    # dann global definierte Reihenfolge
    for p in PROVIDER_ORDER:
        if p in tried:
            continue
        tried.append(p)
        url = _try_get_direct(ep, p, language)
        if url:
            logger.success(f"Using fallback provider '{p}'")
            return url, p

    logger.error(f"No direct link found. Tried providers: {', '.join(tried) or 'none'}")
    raise DownloadError(f"No direct link found. Tried providers: {', '.join(tried) or 'none'}")


def _ydl_download(
    direct_url: str,
    dest_dir: Path,
    *,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
    stop_event: Optional[threading.Event] = None,
) -> Tuple[Path, Dict[str, Any]]:
    logger.info(f"Starting yt-dlp download: url={direct_url}, dest_dir={dest_dir}, title_hint={title_hint}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(dest_dir / (_sanitize_filename(title_hint or "%(title)s") + ".%(ext)s"))
    logger.debug(f"yt-dlp output template: {outtmpl}")
    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "retries": 5,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "noprogress": True,  # CLI-Progress aus, wir nutzen hooks
        "merge_output_format": "mkv",
    }

    def _compound_hook(d: dict):
        if stop_event is not None and stop_event.is_set():
            logger.warning("Download cancelled by stop_event.")
            raise DownloadError("Cancelled")
        if progress_cb:
            try:
                progress_cb(d)
            except Exception as e:
                logger.error(f"Progress callback exception: {e}")

    ydl_opts["progress_hooks"] = [_compound_hook]

    if cookiefile:
        logger.info(f"Using cookiefile: {cookiefile}")
        ydl_opts["cookiefile"] = str(cookiefile)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(direct_url, download=True)
            if info is None:
                logger.error("yt-dlp did not return info dict.")
                raise DownloadError("yt-dlp did not return info dict.")
            filename = ydl.prepare_filename(info)
            logger.success(f"Download finished: {filename}")
        return (Path(filename), info)
    except Exception as e:
        logger.error(f"yt-dlp download failed: {e}")
        raise


def download_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    provider: Optional[Provider] = "VOE", 
    language: Language = "German Dub",
    dest_dir: Path,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
    stop_event: Optional[threading.Event] = None,
) -> Path:
    logger.info(f"Starting download_episode: link={link}, slug={slug}, season={season}, episode={episode}, provider={provider}, language={language}, dest_dir={dest_dir}")
    ep = build_episode(link=link, slug=slug, season=season, episode=episode)

    # Fallback-Strategie
    direct, chosen = get_direct_url_with_fallback(ep, preferred=provider, language=language)
    logger.info(f"Chosen provider: {chosen}, direct URL: {direct}")

    # Sinnvolle Default-Benennung für den temporären Download
    base_hint = title_hint
    if not base_hint and slug and season and episode:
        base_hint = f"{slug}-S{season:02d}E{episode:02d}-{language}-{chosen}"
        logger.debug(f"Generated base_hint for filename: {base_hint}")

    temp_path, info = _ydl_download(
        direct,
        dest_dir,
        title_hint=base_hint,
        cookiefile=cookiefile,
        progress_cb=progress_cb,
        stop_event=stop_event,
    )

    logger.info(f"Download complete, renaming to release schema.")
    final_path = rename_to_release(
        path=temp_path,
        info=info,
        slug=slug,
        season=season,
        episode=episode,
        language=language,
    )
    logger.success(f"Final file path: {final_path}")
    return final_path