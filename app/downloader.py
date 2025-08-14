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

# Lib-API:
from aniworld.models import Anime, Episode  # type: ignore

from app.naming import rename_to_release
from app.config import PROVIDER_ORDER

Language = Literal["German Dub", "German Sub", "English Sub"]
Provider = Literal["VOE", "Vidoza", "Doodstream", "Filemoon", "Vidmoly", "Streamtape", "LoadX", "SpeedFiles", "Luluvdo"]
ProgressCb = Callable[[dict], None]

class DownloadError(Exception):
    pass

class LanguageUnavailableError(DownloadError):
    """Requested language not offered by episode/site."""
    def __init__(self, requested: str, available: List[str]) -> None:
        self.requested = requested
        self.available = available
        super().__init__(f"Language '{requested}' not available. Available: {', '.join(available) or 'none'}")

# ---------------- helpers ----------------

_LANG_ALIASES = {
    # lower -> canonical
    "german": "German Dub",
    "ger": "German Dub",
    "gerdub": "German Dub",
    "dub": "German Dub",

    "germansub": "German Sub",
    "gersub": "German Sub",
    "subde": "German Sub",
    "de-sub": "German Sub",

    "englishsub": "English Sub",
    "engsub": "English Sub",
    "suben": "English Sub",
    "en-sub": "English Sub",
}

def _normalize_language(lang: str | None) -> str:
    if not lang:
        return "German Dub"
    l = re.sub(r"[^a-z]", "", lang.lower())
    return _LANG_ALIASES.get(l, lang)

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

# ----- provider/lang probing ------

_AVAIL_RE = re.compile(r"Available languages:\s*\[([^\]]*)\]", re.IGNORECASE)

def _parse_available_languages_from_error(msg: str) -> List[str]:
    """
    Die Lib loggt u.a.:
      'No provider found for language ... Available languages: ['English Sub', 'German Sub']'
    Das hier extrahiert die Liste robust.
    """
    m = _AVAIL_RE.search(msg or "")
    if not m:
        return []
    raw = m.group(1)
    parts = [p.strip(" '\"\t") for p in raw.split(",") if p.strip()]
    # dedupe & stabile Reihenfolge
    seen = set()
    out: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out

def _try_get_direct(ep: Episode, provider_name: str, language: str) -> Optional[str]:
    language = _normalize_language(language)
    logger.info(f"Trying provider '{provider_name}' for language '{language}'")
    try:
        url = ep.get_direct_link(provider_name, language)  # Lib-API
        if url:
            logger.success(f"Found direct URL from provider '{provider_name}': {url}")
            return url
        else:
            logger.warning(f"Provider '{provider_name}' returned no URL.")
    except Exception as e:
        msg = str(e)
        # Vorzeitiger Abbruch, wenn Sprache grundsätzlich nicht existiert
        if "No provider found for language" in msg:
            available = _parse_available_languages_from_error(msg)
            logger.error(f"Language '{language}' unavailable. Available: {available}")
            raise LanguageUnavailableError(language, available)
        logger.warning(f"Exception from provider '{provider_name}': {msg}")
    return None

def get_direct_url_with_fallback(
    ep: Episode,
    *,
    preferred: Optional[str],
    language: str,
) -> Tuple[str, str]:

    language = _normalize_language(language)
    logger.info(f"Getting direct URL with fallback. Preferred: {preferred}, Language: {language}")
    tried: List[str] = []

    # Early language validation
    available_languages = getattr(ep, 'language_name', None)
    if available_languages is not None:
        if language not in available_languages:
            logger.error(f"Requested language '{language}' not available. Available: {available_languages}")
            raise LanguageUnavailableError(language, available_languages)

    # preferred zuerst (wenn gesetzt)
    if preferred:
        p = preferred.strip()
        if p:
            tried.append(p)
            try:
                url = _try_get_direct(ep, p, language)
            except LanguageUnavailableError as le:
                # sofortiger Abbruch – es ergibt keinen Sinn, weitere Provider zu testen
                raise le
            if url:
                logger.success(f"Using preferred provider '{p}'")
                return url, p

    # dann globale Reihenfolge
    for p in PROVIDER_ORDER:
        if p in tried:
            continue
        tried.append(p)
        try:
            url = _try_get_direct(ep, p, language)
        except LanguageUnavailableError as le:
            raise le
        if url:
            logger.success(f"Using fallback provider '{p}'")
            return url, p

    logger.error(f"No direct link found. Tried providers: {', '.join(tried) or 'none'}")
    raise DownloadError(f"No direct link found. Tried providers: {', '.join(tried) or 'none'}")

# -------- yt-dlp --------

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
        "noprogress": True,
        "merge_output_format": "mkv",
        "fragment_retries": 9999,
        "downloader": "ffmpeg",
        "hls_use_mpegts": True,
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

# -------- public API --------

def download_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    provider: Optional[Provider] = "VOE",
    language: str = "German Dub",
    dest_dir: Path,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
    stop_event: Optional[threading.Event] = None,
) -> Path:
    language = _normalize_language(language)
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