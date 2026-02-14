import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast
from urllib.parse import urlsplit

import yt_dlp
from loguru import logger
from yt_dlp.utils import DownloadError as YTDLPDownloadError

from app.config import DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC
from .errors import DownloadError
from .utils import sanitize_filename
from .types import ProgressCb


def _looks_like_hls_url(url: str) -> bool:
    """Return True when `url` appears to target an HLS playlist."""
    try:
        path = urlsplit(url).path.lower()
    except Exception:
        path = url.lower()
    return path.endswith(".m3u8") or ".m3u8" in path


def _ydl_download(
    direct_url: str,
    dest_dir: Path,
    *,
    title_hint: Optional[str] = None,
    cookiefile: Optional[Path] = None,
    progress_cb: Optional[ProgressCb] = None,
    stop_event: Optional[threading.Event] = None,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Download a media resource with yt-dlp into the given directory and return the downloaded file path and metadata.

    Parameters:
        direct_url (str): Direct media URL or playlist identifier to pass to yt-dlp.
        dest_dir (Path): Destination directory where the download and temporary files will be stored; created if missing.
        title_hint (Optional[str]): Hint for the output filename; sanitized and used as the output template when provided.
        cookiefile (Optional[Path]): Path to a cookies file to supply to yt-dlp for authenticated requests.
        progress_cb (Optional[callable]): Callback invoked with yt-dlp progress dictionaries as they arrive.
        stop_event (Optional[threading.Event]): If set during download, the operation is cancelled and a DownloadError("Cancelled") is raised.
    Returns:
        Tuple[Path, Dict[str, Any]]: The final downloaded file path and the yt-dlp info dictionary.

    Raises:
        DownloadError: On cancellation, timeout, yt-dlp failures, or other unexpected download errors.
    """
    logger.info(
        "Starting yt-dlp download: url={}, dest_dir={}, title_hint={}",
        direct_url,
        dest_dir,
        title_hint,
    )
    dest_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(
        dest_dir / (sanitize_filename(title_hint or "%(title)s") + ".%(ext)s")
    )
    logger.debug("yt-dlp output template: {}", outtmpl)
    concurrent_fragment_downloads = 4
    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "retries": 3,
        "fragment_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": concurrent_fragment_downloads,
        "quiet": True,
        "noprogress": True,
        "merge_output_format": "mkv",
        "downloader": "ffmpeg",
        "hls_use_mpegts": True,
        "socket_timeout": 20,
    }
    if DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC > 0:
        effective_ratelimit = DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC
        if concurrent_fragment_downloads > 1 and _looks_like_hls_url(direct_url):
            # yt-dlp applies ratelimit per concurrent fragment stream.
            effective_ratelimit = max(
                1, DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC // concurrent_fragment_downloads
            )
            logger.info(
                "yt-dlp HLS rate limit normalized: target={} bytes/s, "
                "fragments={}, per_fragment={} bytes/s",
                DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC,
                concurrent_fragment_downloads,
                effective_ratelimit,
            )
        ydl_opts["ratelimit"] = effective_ratelimit
        logger.info(
            "yt-dlp download rate limit enabled: configured={} bytes/s, "
            "effective={} bytes/s",
            DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC,
            effective_ratelimit,
        )

    def _compound_hook(progress: dict) -> None:
        """
        Handle a single yt-dlp progress update: enforce cancellation and forward the progress to the provided callback.

        Parameters:
            progress (dict): Progress information dictionary produced by yt-dlp.

        Raises:
            DownloadError: If a stop event has been set indicating the download should be cancelled.

        Notes:
            If the progress callback raises an exception, it will be caught and suppressed.
        """
        if stop_event is not None and stop_event.is_set():
            logger.warning("Download cancelled by stop_event.")
            raise DownloadError("Cancelled")
        if progress_cb:
            try:
                progress_cb(progress)
            except Exception as exc:
                logger.error("Progress callback exception: {}", exc)

    ydl_opts["progress_hooks"] = [_compound_hook]

    if cookiefile:
        logger.info("Using cookiefile: {}", cookiefile)
        ydl_opts["cookiefile"] = str(cookiefile)

    try:
        ydl_params = cast("yt_dlp.YoutubeDL.Params", ydl_opts)  # type: ignore[arg-type]
        with yt_dlp.YoutubeDL(ydl_params) as ydl:
            info = ydl.extract_info(direct_url, download=True)
            if info is None:
                logger.error("yt-dlp did not return info dict.")
                raise DownloadError("yt-dlp did not return info dict.")
            filename = ydl.prepare_filename(info)
            logger.success("Download finished: {}", filename)
            return Path(filename), cast(Dict[str, Any], info)
    except YTDLPDownloadError as exc:
        logger.error("yt-dlp download failed: {}", exc)
        raise DownloadError(str(exc)) from exc
    except TimeoutError as exc:
        logger.error("yt-dlp timeout: {}", exc)
        raise DownloadError("Timeout") from exc
    except Exception as exc:
        logger.error("yt-dlp unexpected error: {}", exc)
        raise DownloadError("Unexpected error") from exc
