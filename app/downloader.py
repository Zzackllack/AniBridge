from pathlib import Path
from typing import Optional, Literal, Callable, Tuple, Dict, Any
import re
import yt_dlp

# Lib-API laut Doku:
# from aniworld.models import Anime, Episode
# -> get_direct_link(provider, language)
from aniworld.models import Anime, Episode  # type: ignore

from app.naming import rename_to_release

Language = Literal["German Dub", "German Sub", "English Sub"]
Provider = Literal["VOE", "Vidoza", "Doodstream", "Filemoon", "Vidmoly", "Streamtape", "LoadX", "SpeedFiles", "Luluvdo"]
ProgressCb = Callable[[dict], None]  # bekommt yt-dlp progress dict

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

def _ydl_download(
    direct_url: str,
    dest_dir: Path,
    *,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Lädt mit yt-dlp und gibt (Dateipfad, info) zurück.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(dest_dir / (_sanitize_filename(title_hint or "%(title)s") + ".%(ext)s"))
    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "retries": 5,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "noprogress": True,  # CLI-Progress aus, wir nutzen hooks
        "merge_output_format": "mkv",
    }

    if progress_cb:
        def _hook(d: dict):
            try:
                progress_cb(d)
            except Exception:
                pass
        ydl_opts["progress_hooks"] = [_hook]

    if cookiefile:
        ydl_opts["cookiefile"] = str(cookiefile)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(direct_url, download=True)
        if info is None:
            raise DownloadError("yt-dlp did not return info dict.")
        filename = ydl.prepare_filename(info)
    return (Path(filename), info)

def download_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    provider: Provider = "VOE",
    language: Language = "German Dub",
    dest_dir: Path,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> Path:
    ep = build_episode(link=link, slug=slug, season=season, episode=episode)
    direct = get_direct_url(ep, provider, language)
    hint = title_hint or (f"{slug}-S{season:02d}E{episode:02d}-{language}-{provider}"
                          if slug and season and episode else title_hint)

    temp_path, info = _ydl_download(
        direct, dest_dir, title_hint=hint, cookiefile=cookiefile, progress_cb=progress_cb
    )

    # Nach dem Download: in Release-Schema umbenennen
    final_path = rename_to_release(
        path=temp_path,
        info=info,
        slug=slug,
        season=season,
        episode=episode,
        language=language,
    )
    return final_path