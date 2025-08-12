from typing import Optional, Literal
from pathlib import Path
import re
import os
from pathlib import Path
import yt_dlp

# Lib-API laut Doku:
# from aniworld.models import Anime, Episode
# -> get_direct_link(provider, language)
from aniworld.models import Anime, Episode  # type: ignore

DEFAULT_DOWNLOAD_DIR = Path(os.getenv("ANIBRIDGE_DOWNLOAD_DIR", "./data/downloads/anime")).resolve()

Language = Literal["German Dub", "German Sub", "English Sub"]
Provider = Literal["VOE", "Vidoza", "Doodstream", "Filemoon", "Vidmoly", "Streamtape", "LoadX", "SpeedFiles", "Luluvdo"]

class DownloadError(Exception):
    pass

def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()

def build_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None
) -> Episode:
    """
    Entweder direkten Episoden-Link ODER (slug, season, episode) übergeben.
    slug z.B. 'demon-slayer-kimetsu-no-yaiba'
    """
    if link:
        return Episode(link=link)
    if slug and season and episode:
        return Episode(slug=slug, season=season, episode=episode)
    raise ValueError("Provide either link OR (slug, season, episode).")

def get_direct_url(ep: Episode, provider: Provider, language: Language) -> str:
    """
    Ruft den unmittelbaren Video-Link vom Hoster ab.
    """
    url = ep.get_direct_link(provider, language)  # Lib-API lt. Doku
    if not url:
        raise DownloadError("No direct link returned from provider.")
    return url

def download_direct_url(
    direct_url: str,
    dest_dir: Path,
    *,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
) -> Path:
    """
    Lädt mit yt-dlp. Gibt finalen Dateipfad zurück.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(dest_dir / (_sanitize_filename(title_hint or "%(title)s") + ".%(ext)s"))
    ydl_opts = {
        "outtmpl": outtmpl,
        "retries": 5,
        "continuedl": True,
        "noprogress": True,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "merge_output_format": "mkv",  # gute Default-Container
    }
    if cookiefile:
        ydl_opts["cookiefile"] = str(cookiefile)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(direct_url, download=True)
        filename = ydl.prepare_filename(info)
    return Path(filename)

def download_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    provider: Provider = "VOE",
    language: Language = "German Dub",
    dest_dir: Path = DEFAULT_DOWNLOAD_DIR,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
) -> Path:
    ep = build_episode(link=link, slug=slug, season=season, episode=episode)
    direct = get_direct_url(ep, provider, language)
    # sinnvolle Default-Benennung
    hint = title_hint or f"{slug or 'episode'}-S{season:02d}E{episode:02d}-{language}-{provider}" if slug and season and episode else title_hint
    return download_direct_url(direct, dest_dir, title_hint=hint, cookiefile=cookiefile)
