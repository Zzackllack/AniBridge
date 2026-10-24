"""Native yt-dlp transfer only; all requests use VerifiedRH.

Remux/probe run as separate supervised phases after this process exits, so
nested ffmpeg processes cannot multiply the shared child memory allowance.
"""

from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.dependencies import Cryptodome
from yt_dlp.downloader.hls import HlsFD
from yt_dlp.downloader.http import HttpFD
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import DownloadError

from .media_transport import TransferState, VerifiedRH
from .resolution_transport import ResolutionError
from .transfer_progress import TransferProgress, progress_counters  # noqa: F401 -- compatibility import


class ControlledYDL(YoutubeDL):
    def __init__(self, state: TransferState, params: dict) -> None:
        self.transfer_state = state
        super().__init__(params, auto_init=False)

    def build_request_director(self, handlers, preferences=None):
        # There is deliberately no second handler if our transport refuses a URL.
        return super().build_request_director(
            (lambda **kwargs: VerifiedRH(state=self.transfer_state, **kwargs),)
        )


class NativeVod(HlsFD):
    def real_download(self, filename, info_dict):
        with self.ydl.urlopen(info_dict["url"]) as response:
            manifest = response.read().decode("utf-8", errors="strict")
            source_url = response.url
        if "#EXT-X-ENDLIST" not in manifest or not self.can_download(
            manifest, info_dict
        ):
            raise ResolutionError("extraction_error")
        if "#EXT-X-KEY:METHOD=AES-128" in manifest and not Cryptodome.AES:
            raise ResolutionError("extraction_error")
        # Supplying the same verified manifest keeps the inherited implementation
        # on its native path. Its ffmpeg fallback conditions were rejected above.
        return super().real_download(
            filename,
            {**info_dict, "url": source_url, "hls_media_playlist_data": manifest},
        )


class SilentLog:
    def debug(self, message):
        pass

    info = warning = error = debug


def transfer(
    url: str, directory: Path, progress, *, bandwidth: int | None = None
) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    state = TransferState(directory)
    params = {
        "logger": SilentLog(),
        "quiet": True,
        "noprogress": True,
        "proxy": "",
        "external_downloader": "native",
        "hls_prefer_native": True,
        "concurrent_fragment_downloads": 1,
        "retries": 0,
        "fragment_retries": 0,
        "skip_unavailable_fragments": False,
        "continuedl": False,
        "ratelimit": bandwidth,
        "socket_timeout": 120,
        "writeinfojson": False,
        "writethumbnail": False,
    }
    outputs = []
    try:
        with ControlledYDL(state, params) as ydl:
            with ydl.urlopen(url) as response:
                beginning = response.read(512)
            if beginning.lstrip().startswith(b"#EXTM3U"):
                extractor = InfoExtractor(ydl)
                formats = extractor._extract_m3u8_formats(
                    url, "local", ext="mp4", entry_protocol="m3u8_native"
                )
                videos = [item for item in formats if item.get("vcodec") != "none"]
                if not videos:
                    raise ResolutionError("extraction_error")
                # Select only among metadata that the manifest actually supplied.
                video = max(
                    videos,
                    key=lambda item: (item.get("height") or 0, item.get("tbr") or 0),
                )
                selected = [video]
                if video.get("acodec") == "none":
                    audio = [item for item in formats if item.get("vcodec") == "none"]
                    if not audio:
                        raise ResolutionError("extraction_error")
                    selected.append(max(audio, key=lambda item: item.get("tbr") or 0))
            else:
                selected = [{"url": url, "protocol": "https", "ext": "bin"}]
            tracker = TransferProgress(selected)
            for number, item in enumerate(selected):
                if item.get("protocol") not in ("https", "m3u8_native"):
                    raise ResolutionError("extraction_error")
                output = directory / f"track-{number}.partial-media"
                downloader = (
                    NativeVod if item["protocol"] == "m3u8_native" else HttpFD
                )(ydl, params)

                def update(values, index=number):
                    if values.get("status") in ("downloading", "finished"):
                        progress(tracker.update(index, values))

                downloader.add_progress_hook(update)
                success, _ = downloader.download(
                    str(output), {**item, "id": "local", "title": "local"}
                )
                if not success or not output.is_file():
                    raise ResolutionError(state.error or "extraction_error")
                progress(tracker.finish(number, output.stat().st_size))
                outputs.append(output)
        return outputs
    except DownloadError:
        raise ResolutionError(state.error or "extraction_error") from None
