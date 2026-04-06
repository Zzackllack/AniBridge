import threading
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from app.config import PROVIDER_ORDER
from app.utils.naming import rename_to_release
from app.providers.megakino.client import get_default_client
from .errors import DownloadError
from .episode import build_episode
from .language import normalize_language
from .provider_resolution import get_direct_url_with_fallback
from .types import Provider, ProgressCb
from .ytdlp import _ydl_download


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
    Download an episode to the specified directory, resolving a direct stream URL with provider fallback logic.

    This function builds an Episode from the provided identifiers, attempts to
    resolve a direct download URL (optionally preferring a provider), downloads
    the media via yt-dlp with progress callbacks and cancellation support, and
    renames the downloaded file into the repository's release naming schema. If
    extraction or download fails, controlled fallback attempts are performed
    across alternate providers before failing.

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
    language = normalize_language(language)
    release_override = None
    if title_hint:
        cleaned = title_hint.replace(" [STRM]", "").strip()
        release_override = cleaned if cleaned else None
    logger.info(
        "Starting download_episode: link={}, slug={}, season={}, episode={}, provider={}, language={}, dest_dir={}, site={}",
        link,
        slug,
        season,
        episode,
        provider,
        language,
        dest_dir,
        site,
    )
    if "megakino" in site and slug:
        logger.debug("Megakino download flow: slug='{}'", slug)
        client = get_default_client()
        entry = client.load_index().get(slug)
        is_movie = bool(entry and entry.kind == "film")
        if is_movie:
            logger.debug("Megakino slug '{}' classified as movie.", slug)
        provider_candidates = []
        if provider:
            provider_candidates.append(provider)
        for prov_name in PROVIDER_ORDER:
            if prov_name not in provider_candidates:
                provider_candidates.append(prov_name)
        if not provider_candidates:
            provider_candidates = [None]

        tried_direct: set[str] = set()
        last_error: Optional[Exception] = None

        def _attempt_download(
            *,
            preferred_provider: Optional[str],
        ) -> Optional[Path]:
            """
            Resolve Megakino direct URL and download once for one provider.

            Resolves a direct URL for the preferred provider, downloads to
            `dest_dir` via yt-dlp, then renames the file to the release schema
            (movie vs episode aware).

            Parameters:
                preferred_provider (Optional[str]): Preferred provider; `None`
                    lets the resolver choose.

            Returns:
                Path or None: Final renamed path, or `None` when the resolved
                direct URL was already tried.
            """
            direct, chosen = client.resolve_direct_url(
                slug=slug, preferred_provider=preferred_provider
            )
            if direct in tried_direct:
                logger.debug("Megakino direct URL already tried; skipping: {}", direct)
                return None
            tried_direct.add(direct)
            logger.debug(
                "Megakino download direct URL: provider={} url={}", chosen, direct
            )
            base_hint = title_hint
            if not base_hint:
                if is_movie:
                    base_hint = f"{slug}-{language}-{chosen}"
                elif slug and season is not None and episode is not None:
                    base_hint = (
                        f"{slug}-S{season:02d}E{episode:02d}-{language}-{chosen}"
                    )
            temp_path, info = _ydl_download(
                direct,
                dest_dir,
                title_hint=base_hint,
                cookiefile=cookiefile,
                progress_cb=progress_cb,
                stop_event=stop_event,
            )
            final_path = rename_to_release(
                path=temp_path,
                info=info,
                slug=slug,
                season=None if is_movie else season,
                episode=None if is_movie else episode,
                language=language,
                site=site,
                release_name_override=release_override,
            )
            logger.success("Final file path: {}", final_path)
            return final_path

        for preferred_provider in provider_candidates:
            try:
                result = _attempt_download(preferred_provider=preferred_provider)
                if result is not None:
                    return result
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Megakino download attempt failed (provider={}): {}",
                    preferred_provider,
                    exc,
                )

        raise DownloadError(
            f"Megakino download failed after retries: {last_error}"
        ) from last_error
    ep = build_episode(link=link, slug=slug, season=season, episode=episode, site=site)

    direct, chosen = get_direct_url_with_fallback(
        ep, preferred=provider, language=language
    )
    logger.info("Chosen provider: {}, direct URL: {}", chosen, direct)

    base_hint = title_hint
    if not base_hint and slug and season is not None and episode is not None:
        base_hint = f"{slug}-S{season:02d}E{episode:02d}-{language}-{chosen}"
        logger.debug("Generated base_hint for filename: {}", base_hint)

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
        )
    except Exception as exc:
        msg = str(exc)
        logger.warning("Primary download failed: {}", msg)

        tried_alt = False
        providers_left = [
            provider_name
            for provider_name in PROVIDER_ORDER
            if provider_name != (provider or "")
        ]
        for provider_name in providers_left:
            try:
                direct3, chosen3 = get_direct_url_with_fallback(
                    ep, preferred=provider_name, language=language
                )
                logger.info("Retrying download via alternate provider {}", chosen3)
                temp_path, info = _ydl_download(
                    direct3,
                    dest_dir,
                    title_hint=base_hint,
                    cookiefile=cookiefile,
                    progress_cb=progress_cb,
                    stop_event=stop_event,
                )
                tried_alt = True
                break
            except Exception as exc3:
                logger.warning(
                    "Alternate provider {} failed to download: {}",
                    provider_name,
                    exc3,
                )

        if not tried_alt:
            raise

    if temp_path is None or info is None:
        logger.error("Download completed without producing a temp file or info dict.")
        raise DownloadError("Download failed: no temp file or metadata produced.")

    logger.info("Download complete, renaming to release schema.")
    final_path = rename_to_release(
        path=temp_path,
        info=info,
        slug=slug,
        season=season,
        episode=episode,
        language=language,
        site=site,
        release_name_override=release_override,
    )
    logger.success("Final file path: {}", final_path)
    return final_path
