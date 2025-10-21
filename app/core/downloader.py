import os
import sys
from pathlib import Path
from typing import Optional, Literal, Callable, Tuple, Dict, Any, List, cast
import re
import threading
import yt_dlp
from yt_dlp.utils import DownloadError as YTDLPDownloadError
from loguru import logger
from app.utils.logger import config as configure_logger

configure_logger()

# Lib-API:
from aniworld.models import Anime, Episode  # type: ignore

from app.utils.naming import rename_to_release
from app.config import PROVIDER_ORDER, PROXY_ENABLED, PROXY_SCOPE
from app.infrastructure.network import yt_dlp_proxy, disabled_proxy_env

Language = Literal["German Dub", "German Sub", "English Sub", "English Dub"]
Provider = Literal[
    "VOE",
    "Vidoza",
    "Doodstream",
    "Filemoon",
    "Vidmoly",
    "Streamtape",
    "LoadX",
    "SpeedFiles",
    "Luluvdo",
]
ProgressCb = Callable[[dict], None]


class DownloadError(Exception):
    pass


class LanguageUnavailableError(DownloadError):
    """Requested language not offered by episode/site."""

    def __init__(self, requested: str, available: List[str]) -> None:
        self.requested = requested
        self.available = available
        super().__init__(
            f"Language '{requested}' not available. Available: {', '.join(available) or 'none'}"
        )


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
    "englishdub": "English Dub",
    "engdub": "English Dub",
    "duben": "English Dub",
    "en-dub": "English Dub",
    "endub": "English Dub",
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
    episode: Optional[int] = None,
    site: str = "aniworld.to",
) -> Episode:
    """
    Construct an Episode from either a direct link or a slug/season/episode triple for the specified site.

    Parameters:
        link (Optional[str]): Direct episode URL; used when provided and takes precedence over slug/season/episode.
        slug (Optional[str]): Series identifier used with `season` and `episode` when `link` is not provided.
        season (Optional[int]): Season number paired with `slug` and `episode`.
        episode (Optional[int]): Episode number paired with `slug` and `season`.
        site (str): Host site identifier to attach to the created Episode (default: "aniworld.to").

    Returns:
        Episode: The constructed Episode using the provided inputs.

    Raises:
        ValueError: If neither `link` nor the combination of `slug`, `season`, and `episode` are supplied.
    """
    logger.info(
        f"Building episode: link={link}, slug={slug}, season={season}, episode={episode}, site={site}"
    )
    ep: Optional[Episode] = None
    if link:
        logger.debug("Using direct link for episode.")
        ep = Episode(link=link, site=site)
    elif slug and season and episode:
        logger.debug("Using slug/season/episode for episode.")
        ep = Episode(slug=slug, season=season, episode=episode, site=site)
    else:
        logger.error(
            "Invalid episode parameters: must provide either link or (slug, season, episode)."
        )
        raise ValueError("Provide either link OR (slug, season, episode).")

    # aniworld>=3.6.4 stopped auto-populating basic details when instantiated
    # via slug/season/episode. When link stays None the provider scrape later
    # fails. Force-run the helper if available.
    if getattr(ep, "link", None) is None:
        logger.warning(
            "Episode link is None after init; attempting to auto-fill basic details. Are you using aniworld>=3.6.4?"
        )
        auto_basic = getattr(ep, "_auto_fill_basic_details", None)
        if callable(auto_basic):
            logger.warning(
                "Running _auto_fill_basic_details() to populate episode basics."
            )
            # Guard against the flag short-circuiting the helper.
            if getattr(ep, "_basic_details_filled", False):
                setattr(ep, "_basic_details_filled", False)
                logger.warning("Reset _basic_details_filled flag to False.")
            try:
                auto_basic()
                logger.warning("Successfully populated episode basics.")
            except Exception as err:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to populate episode basics (slug=%s, season=%s, episode=%s): %s",
                    getattr(ep, "slug", slug),
                    getattr(ep, "season", season),
                    getattr(ep, "episode", episode),
                    err,
                )
    return ep


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
    """
    Resolve a direct download URL for an episode, trying a preferred provider first and falling back to the configured provider order.

    Parameters:
        ep (Episode): Episode object to resolve the direct link for.
        preferred (Optional[str]): Provider name to try first; ignored if empty or None.
        language (str): Desired language label; will be normalized before use.

    Returns:
        tuple: (direct_url, provider_name) where `direct_url` is the resolved URL and `provider_name` is the provider that supplied it.

    Raises:
        LanguageUnavailableError: If the requested language is not offered by the episode or a provider indicates the language is unavailable.
        DownloadError: If no provider yields a direct URL after all fallbacks.
    """
    language = _normalize_language(language)
    logger.info(
        f"Getting direct URL with fallback. Preferred: {preferred}, Language: {language}"
    )
    tried: List[str] = []

    # Early language validation
    _langs = (
        getattr(ep, "language_name", None)
        or getattr(ep, "languages", None)
        or getattr(ep, "available_languages", None)
    )
    if not _langs:
        # AniWorld >=3.6.4 no longer auto-populates language metadata during __init__.
        # See https://github.com/phoenixthrush/AniWorld-Downloader/issues/98
        # Fixed in >=3.7.1, see https://github.com/phoenixthrush/AniWorld-Downloader/pull/100
        # Try known auto-fill helpers defensively.
        for _auto_name in ("auto_fill_details", "_auto_fill_basic_details", "auto_fill_basic_details"):
            _auto = getattr(ep, _auto_name, None)
            if callable(_auto):
                try:
                    _auto()
                    break
                except Exception as err:  # pragma: no cover - defensive
                    logger.warning(
                        "Failed to auto-fill episode details using %s(): %s",
                        _auto_name,
                        err,
                    )
        _langs = (
            getattr(ep, "language_name", None)
            or getattr(ep, "languages", None)
            or getattr(ep, "available_languages", None)
        )

    if _langs is not None:
        if isinstance(_langs, str):
            _langs_iter = [_langs]
        else:
            try:
                _langs_iter = list(_langs)
            except Exception:
                _langs_iter = None
        if _langs_iter is not None and language not in _langs_iter:
            logger.error(
                f"Requested language '{language}' not available. Available: {_langs_iter}"
            )
            raise LanguageUnavailableError(language, _langs_iter)

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
    raise DownloadError(
        f"No direct link found. Tried providers: {', '.join(tried) or 'none'}"
    )


# -------- yt-dlp --------


def _ydl_download(
    direct_url: str,
    dest_dir: Path,
    *,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
    stop_event: Optional[threading.Event] = None,
    force_no_proxy: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Download a media resource via yt-dlp and return the downloaded file path and metadata.

    Uses yt-dlp to download the resource at `direct_url` into `dest_dir`, applying an optional filename hint, cookiefile, proxy configuration, progress callbacks, and cancellation via `stop_event`.

    Parameters:
        direct_url (str): Direct media URL or playlist identifier to pass to yt-dlp.
        dest_dir (Path): Directory where the download and temporary files will be stored; created if missing.
        title_hint (Optional[str]): Hint for the output filename; sanitized and used in the output template if provided.
        cookiefile (Optional[Path]): Path to a cookies file to supply to yt-dlp for authenticated requests.
        progress_cb (Optional[callable]): Callback invoked with yt-dlp progress dictionaries as they arrive.
        stop_event (Optional[threading.Event]): If set during download, the operation will be cancelled and raise DownloadError("Cancelled").
        force_no_proxy (bool): When true, disable any configured proxy for this yt-dlp invocation.

    Returns:
        Tuple[Path, Dict[str, Any]]: A tuple containing the final downloaded file path and the yt-dlp info dictionary.
    """
    logger.info(
        f"Starting yt-dlp download: url={direct_url}, dest_dir={dest_dir}, title_hint={title_hint}"
    )
    dest_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(
        dest_dir / (_sanitize_filename(title_hint or "%(title)s") + ".%(ext)s")
    )
    logger.debug(f"yt-dlp output template: {outtmpl}")
    # Keep retries conservative to avoid endless retry loops on dead links
    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "retries": 3,  # whole-request retries
        "fragment_retries": 3,  # per-fragment retries
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "noprogress": True,
        "merge_output_format": "mkv",
        "downloader": "ffmpeg",
        "hls_use_mpegts": True,
        # Fail faster on broken CDNs
        "socket_timeout": 20,
    }

    # Apply proxy for yt-dlp if configured
    try:
        if not force_no_proxy:
            proxy_url = yt_dlp_proxy()
            if proxy_url:
                ydl_opts["proxy"] = proxy_url
                logger.info(f"yt-dlp proxy enabled: {proxy_url}")
        else:
            logger.info("yt-dlp proxy disabled by fallback policy")
    except Exception as e:
        logger.debug(f"yt-dlp proxy configuration failed: {e}")

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
        # yt_dlp.YoutubeDL expects a specific Params type; cast to satisfy type checkers.
        # Keep a runtime-safe cast so the dict is passed unchanged at runtime.
        ydl_params = cast("yt_dlp.YoutubeDL.Params", ydl_opts)  # type: ignore[arg-type]
        with yt_dlp.YoutubeDL(ydl_params) as ydl:
            info = ydl.extract_info(direct_url, download=True)
            if info is None:
                logger.error("yt-dlp did not return info dict.")
                raise DownloadError("yt-dlp did not return info dict.")
            filename = ydl.prepare_filename(info)
            logger.success(f"Download finished: {filename}")
            # return the downloaded file path and the info dict to satisfy the declared return type
            return Path(filename), cast(Dict[str, Any], info)
    except YTDLPDownloadError as e:
        logger.error(f"yt-dlp download failed: {e}")
        raise DownloadError(str(e))
    except TimeoutError as e:
        logger.error(f"yt-dlp timeout: {e}")
        raise DownloadError("Timeout") from e
    except Exception as e:  # noqa: BLE001 — unexpected failures
        logger.error(f"yt-dlp unexpected error: {e}")
        raise DownloadError("Unexpected error") from e


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
    site: str = "aniworld.to",
) -> Path:
    """
    Download an episode to the specified directory, resolving a direct stream URL with provider fallback and proxy-aware retry logic.

    This function builds an Episode from the provided identifiers, attempts to resolve a direct download URL (optionally preferring a provider), downloads the media via yt-dlp with progress callbacks and cancellation support, and renames the downloaded file into the repository's release naming schema. If extraction or download fails, controlled fallback attempts are performed (no-proxy re-resolution and alternate providers) before failing.

    Parameters:
        link (Optional[str]): Direct episode page URL; if provided, used instead of slug/season/episode.
        slug (Optional[str]): Series identifier used to construct an Episode when `link` is not given.
        season (Optional[int]): Season number to construct an Episode when `link` is not given.
        episode (Optional[int]): Episode number to construct an Episode when `link` is not given.
        provider (Optional[Provider]): Preferred provider name to try first when resolving a direct URL.
        language (str): Desired language label (will be normalized); used when resolving available streams.
        dest_dir (Path): Destination directory where the temporary download will be written.
        title_hint (Optional[str]): Hint for the temporary output filename; if omitted and slug/season/episode are given, a default is generated.
        cookiefile (Optional[Path]): Path to a cookies file passed to yt-dlp, if required by the provider/site.
        progress_cb (Optional[ProgressCb]): Optional callback that receives yt-dlp progress dictionaries.
        stop_event (Optional[threading.Event]): Optional event that, when set, requests download cancellation.
        site (str): Site identifier to use when constructing the Episode (defaults to "aniworld.to").

    Returns:
        Path: Final path to the renamed release file.

    Raises:
        DownloadError: When URL resolution or download ultimately fails after all fallback attempts.
    """
    language = _normalize_language(language)
    logger.info(
        f"Starting download_episode: link={link}, slug={slug}, season={season}, episode={episode}, provider={provider}, language={language}, dest_dir={dest_dir}, site={site}"
    )
    ep = build_episode(link=link, slug=slug, season=season, episode=episode, site=site)

    # Fallback-Strategie (with proxy-aware retry)
    force_no_proxy = False
    try:
        direct, chosen = get_direct_url_with_fallback(
            ep, preferred=provider, language=language
        )
        logger.info(f"Chosen provider: {chosen}, direct URL: {direct}")
    except DownloadError as e:
        # If proxy is enabled and extraction failed completely, try a last-resort
        # direct path (no proxy) so the job can still succeed. This keeps both
        # extraction and download on the same (direct) IP to avoid CDN 403.
        if PROXY_ENABLED and PROXY_SCOPE in ("all", "ytdlp"):
            logger.warning(
                f"Direct link not found under proxy ({e}). Attempting direct fallback without proxy."
            )
            with disabled_proxy_env():
                ep2 = build_episode(
                    link=link, slug=slug, season=season, episode=episode, site=site
                )
                direct, chosen = get_direct_url_with_fallback(
                    ep2, preferred=provider, language=language
                )
                logger.info(
                    f"Fallback (no proxy) chose provider: {chosen}, direct URL: {direct}"
                )
                force_no_proxy = True
        else:
            raise

    # Sinnvolle Default-Benennung für den temporären Download
    base_hint = title_hint
    if not base_hint and slug and season and episode:
        base_hint = f"{slug}-S{season:02d}E{episode:02d}-{language}-{chosen}"
        logger.debug(f"Generated base_hint for filename: {base_hint}")

    # ensure variables exist for static analyzers / linters
    temp_path: Optional[Path] = None
    info: Optional[Dict[str, Any]] = None

    try:
        temp_path, info = _ydl_download(
            direct,
            dest_dir,
            title_hint=base_hint,
            cookiefile=cookiefile,
            progress_cb=progress_cb,
            stop_event=stop_event,
            force_no_proxy=force_no_proxy,
        )
    except Exception as e:
        # If the actual download fails (timeouts/CDN issues), try one controlled
        # fallback path before giving up:
        #  1) If we used proxy, re-resolve and download without proxy consistently
        #  2) Otherwise, try to re-resolve with a different provider if available
        msg = str(e)
        logger.warning(f"Primary download failed: {msg}")

        # Attempt no-proxy re-resolution+download if proxy was in play
        tried_alt = False
        if PROXY_ENABLED and not force_no_proxy and PROXY_SCOPE in ("all", "ytdlp"):
            try:
                with disabled_proxy_env():
                    ep2 = build_episode(
                        link=link, slug=slug, season=season, episode=episode, site=site
                    )
                    direct2, chosen2 = get_direct_url_with_fallback(
                        ep2, preferred=provider, language=language
                    )
                    logger.info(
                        f"Retrying download without proxy using provider {chosen2}"
                    )
                    temp_path, info = _ydl_download(
                        direct2,
                        dest_dir,
                        title_hint=base_hint,
                        cookiefile=cookiefile,
                        progress_cb=progress_cb,
                        stop_event=stop_event,
                        force_no_proxy=True,
                    )
                    tried_alt = True
            except Exception as e2:
                logger.error(f"No-proxy fallback download failed: {e2}")
                # fall through to final error or other alt attempts

        if not tried_alt:
            # As a last resort, try a different provider once (if any available)
            try:
                providers_left = [p for p in PROVIDER_ORDER if p != (provider or "")]
                for p in providers_left:
                    try:
                        direct3, chosen3 = get_direct_url_with_fallback(
                            ep, preferred=p, language=language
                        )
                        logger.info(
                            f"Retrying download via alternate provider {chosen3}"
                        )
                        temp_path, info = _ydl_download(
                            direct3,
                            dest_dir,
                            title_hint=base_hint,
                            cookiefile=cookiefile,
                            progress_cb=progress_cb,
                            stop_event=stop_event,
                            force_no_proxy=force_no_proxy,
                        )
                        tried_alt = True
                        break
                    except Exception as e3:
                        logger.warning(
                            f"Alternate provider {p} failed to download: {e3}"
                        )
            except Exception as e4:
                logger.debug(f"Alternate-provider resolution failed: {e4}")

        if not tried_alt:
            # Give up with the original failure
            raise

    # Safety check for linters: ensure temp_path and info are set
    if temp_path is None or info is None:
        logger.error("Download completed without producing a temp file or info dict.")
        raise DownloadError("Download failed: no temp file or metadata produced.")

    logger.info(f"Download complete, renaming to release schema.")
    final_path = rename_to_release(
        path=temp_path,
        info=info,
        slug=slug,
        season=season,
        episode=episode,
        language=language,
        site=site,
    )
    logger.success(f"Final file path: {final_path}")
    return final_path
