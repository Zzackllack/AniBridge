import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast

import yt_dlp
from loguru import logger
from yt_dlp.utils import DownloadError as YTDLPDownloadError

from app.infrastructure.network import yt_dlp_proxy
from .errors import DownloadError
from .utils import sanitize_filename
from .types import ProgressCb


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
    Download a media resource with yt-dlp into the given directory and return the downloaded file path and metadata.

    Parameters:
        direct_url (str): Direct media URL or playlist identifier to pass to yt-dlp.
        dest_dir (Path): Destination directory where the download and temporary files will be stored; created if missing.
        title_hint (Optional[str]): Hint for the output filename; sanitized and used as the output template when provided.
        cookiefile (Optional[Path]): Path to a cookies file to supply to yt-dlp for authenticated requests.
        progress_cb (Optional[callable]): Callback invoked with yt-dlp progress dictionaries as they arrive.
        stop_event (Optional[threading.Event]): If set during download, the operation is cancelled and a DownloadError("Cancelled") is raised.
        force_no_proxy (bool): When true, disable any configured proxy for this yt-dlp invocation.

    Returns:
        Tuple[Path, Dict[str, Any]]: The final downloaded file path and the yt-dlp info dictionary.

    Raises:
        DownloadError: On cancellation, timeout, yt-dlp failures, or other unexpected download errors.
    """
    logger.info(
        "Starting yt-dlp download: url=%s, dest_dir=%s, title_hint=%s",
        direct_url,
        dest_dir,
        title_hint,
    )
    dest_dir.mkdir(parents=True, exist_ok=True)

    outtmpl = str(
        dest_dir / (sanitize_filename(title_hint or "%(title)s") + ".%(ext)s")
    )
    logger.debug("yt-dlp output template: %s", outtmpl)
    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "retries": 3,
        "fragment_retries": 3,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "noprogress": True,
        "merge_output_format": "mkv",
        "downloader": "ffmpeg",
        "hls_use_mpegts": True,
        "socket_timeout": 20,
    }

    try:
        if not force_no_proxy:
            proxy_url = yt_dlp_proxy()
            if proxy_url:
                ydl_opts["proxy"] = proxy_url
                logger.info("yt-dlp proxy enabled: %s", proxy_url)
        else:
            logger.info("yt-dlp proxy disabled by fallback policy")
    except Exception as exc:
        logger.debug("yt-dlp proxy configuration failed: %s", exc)

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
                logger.error("Progress callback exception: %s", exc)

    ydl_opts["progress_hooks"] = [_compound_hook]

    if cookiefile:
        logger.info("Using cookiefile: %s", cookiefile)
        ydl_opts["cookiefile"] = str(cookiefile)

    try:
        ydl_params = cast("yt_dlp.YoutubeDL.Params", ydl_opts)  # type: ignore[arg-type]
        with yt_dlp.YoutubeDL(ydl_params) as ydl:
            info = ydl.extract_info(direct_url, download=True)
            if info is None:
                logger.error("yt-dlp did not return info dict.")
                raise DownloadError("yt-dlp did not return info dict.")
            filename = ydl.prepare_filename(info)
            logger.success("Download finished: %s", filename)
            return Path(filename), cast(Dict[str, Any], info)
    except YTDLPDownloadError as exc:
        logger.error("yt-dlp download failed: %s", exc)
        raise DownloadError(str(exc)) from exc
    except TimeoutError as exc:
        logger.error("yt-dlp timeout: %s", exc)
        raise DownloadError("Timeout") from exc
    except Exception as exc:
        logger.error("yt-dlp unexpected error: %s", exc)
        raise DownloadError("Unexpected error") from exc
