from pathlib import Path
from typing import Optional, Literal, Callable, Tuple, Dict, Any, List
import re
import yt_dlp

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

def _try_get_direct(ep: Episode, provider_name: str, language: Language) -> Optional[str]:
    """
    Einzelnen Provider testen. Gibt URL oder None zurück.
    """
    try:
        url = ep.get_direct_link(provider_name, language)  # Lib-API
        if url:
            return url
    except Exception:
        # still weiterprobieren
        pass
    return None

def get_direct_url_with_fallback(
    ep: Episode,
    *,
    preferred: Optional[str],
    language: Language,
) -> Tuple[str, str]:
    """
    Liefert (direct_url, chosen_provider).
    Reihenfolge: preferred -> ENV PROVIDER_ORDER (ohne Duplikate).
    """
    tried: List[str] = []

    # preferred zuerst (wenn gesetzt)
    if preferred:
        p = preferred.strip()
        if p:
            tried.append(p)
            url = _try_get_direct(ep, p, language)
            if url:
                return url, p

    # dann global definierte Reihenfolge
    for p in PROVIDER_ORDER:
        if p in tried:
            continue
        tried.append(p)
        url = _try_get_direct(ep, p, language)
        if url:
            return url, p

    raise DownloadError(f"No direct link found. Tried providers: {', '.join(tried) or 'none'}")

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
    provider: Optional[Provider] = "VOE", 
    language: Language = "German Dub",
    dest_dir: Path,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> Path:
    """
    Versucht zuerst 'provider' (wenn übergeben), dann die Reihenfolge aus PROVIDER_ORDER (ENV).
    """
    ep = build_episode(link=link, slug=slug, season=season, episode=episode)

    # Fallback-Strategie
    direct, chosen = get_direct_url_with_fallback(ep, preferred=provider, language=language)

    # Sinnvolle Default-Benennung für den temporären Download
    base_hint = title_hint
    if not base_hint and slug and season and episode:
        base_hint = f"{slug}-S{season:02d}E{episode:02d}-{language}-{chosen}"

    temp_path, info = _ydl_download(
        direct,
        dest_dir,
        title_hint=base_hint,
        cookiefile=cookiefile,
        progress_cb=progress_cb
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