"""Best-effort byte estimates from bounded HLS playlist and segment metadata.

The 10-second budget bounds scheduling and streamed reads cooperatively. DNS
resolution can still block; each HTTP operation has a 3-second inactivity
ceiling. The parent supervisor enforces the download-inactivity deadline even
if DNS blocks the download child.
"""

import math
import time
from urllib.parse import urljoin

from yt_dlp import YoutubeDL
from yt_dlp.downloader.hls import HlsFD
from yt_dlp.networking.common import Request

from .media_transport import TransferState

MAX_PLAYLIST_BYTES = 1024 * 1024
MAX_TRACKS = 16
MAX_WALL_SECONDS = 10.0
MAX_REQUEST_TIMEOUT_SECONDS = 3.0
MAX_ESTIMATED_BYTES = 2**63 - 1


def preflight_hls_track_sizes(
    items: list[dict], ydl: YoutubeDL, state: TransferState
) -> None:
    """Seed unknown HLS sizes from one verified HEAD sample per selected track.

    Playlist and HEAD failures are optional metadata failures: restore transfer
    state so yt-dlp's real download can still report the authoritative outcome.
    """
    if not 1 <= len(items) <= MAX_TRACKS:
        return

    deadline = time.monotonic() + MAX_WALL_SECONDS
    for item in items:
        if item.get("protocol") != "m3u8_native" or _known_size(item):
            continue
        if time.monotonic() >= deadline:
            break

        prior_error, prior_timeout, prior_deadline = (
            state.error,
            state.timeout_s,
            state.deadline_s,
        )
        try:
            playlist = _read_playlist(item, ydl, state, deadline)
            if playlist is None:
                continue
            manifest, playlist_url, segment_count, first_segment = playlist
            # Reuse the verified, final-URL-relative manifest in NativeVod.
            item["url"] = playlist_url
            item["hls_media_playlist_data"] = manifest

            timeout = _remaining_timeout(deadline)
            if timeout is None:
                break
            state.timeout_s = timeout
            state.deadline_s = deadline
            with ydl.urlopen(Request(first_segment, method="HEAD")) as response:
                if response.status != 200 or response.headers.get("Content-Range"):
                    continue
                content_length = _content_length(response.headers.get("Content-Length"))
            if content_length is None:
                continue
            estimate = content_length * segment_count
            if 0 < estimate <= MAX_ESTIMATED_BYTES:
                item["filesize_approx"] = estimate
        except Exception:
            # This probe must never turn an otherwise usable transfer into an
            # error. The selected URL and every downloaded segment are still
            # validated by the normal verified handler.
            continue
        finally:
            state.error = prior_error
            state.timeout_s = prior_timeout
            state.deadline_s = prior_deadline


def _read_playlist(
    item: dict, ydl: YoutubeDL, state: TransferState, deadline: float
) -> tuple[str, str, int, str] | None:
    timeout = _remaining_timeout(deadline)
    if timeout is None:
        return None
    state.timeout_s = timeout
    state.deadline_s = deadline
    with ydl.urlopen(item["url"]) as response:
        playlist_url = response.url
        chunks = bytearray()
        while len(chunks) <= MAX_PLAYLIST_BYTES:
            timeout = _remaining_timeout(deadline)
            if timeout is None:
                return None
            state.timeout_s = timeout
            chunk = response.read(min(64 * 1024, MAX_PLAYLIST_BYTES + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)

    if len(chunks) > MAX_PLAYLIST_BYTES:
        return None
    try:
        manifest = chunks.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None
    playlist = _playlist_sample(manifest, playlist_url, item)
    if playlist is None:
        return None
    segment_count, first_segment = playlist
    return manifest, playlist_url, segment_count, first_segment


def _playlist_sample(
    manifest: str, playlist_url: str, item: dict
) -> tuple[int, str] | None:
    if (
        "#EXTM3U" not in manifest.splitlines()[:2]
        or "#EXT-X-TARGETDURATION:" not in manifest
        or not has_endlist_tag(manifest)
        or "#EXT-X-STREAM-INF:" in manifest
        or "#EXT-X-BYTERANGE:" in manifest
        or "#EXT-X-MAP:" in manifest
        or "#EXT-X-KEY:" in manifest
        or "#ANVATO-SEGMENT-INFO" in manifest
        or "#UPLYNK-SEGMENT" in manifest
        or not HlsFD.can_download(manifest, item)
    ):
        return None

    segments = [
        line.strip()
        for line in manifest.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not segments:
        return None
    return len(segments), urljoin(playlist_url, segments[0])


def has_endlist_tag(manifest: str) -> bool:
    return any(line.strip() == "#EXT-X-ENDLIST" for line in manifest.splitlines())


def _known_size(item: dict) -> bool:
    for key in ("filesize", "filesize_approx"):
        value = item.get(key)
        if type(value) in (int, float) and math.isfinite(value) and value > 0:
            return True
    return False


def _content_length(value: str | None) -> int | None:
    if value is None or not value.isascii() or not value.isdecimal():
        return None
    length = int(value)
    return length if length > 0 else None


def _remaining_timeout(deadline: float) -> float | None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    return min(MAX_REQUEST_TIMEOUT_SECONDS, remaining)
