"""Native yt-dlp transfer only; all requests use VerifiedRH.

Remux/probe run as separate supervised phases after this process exits, so
nested ffmpeg processes cannot multiply the shared child memory allowance.
"""

import json
import os
from pathlib import Path
from urllib.parse import urljoin

from yt_dlp import YoutubeDL
from yt_dlp.dependencies import Cryptodome
from yt_dlp.downloader.hls import HlsFD
from yt_dlp.downloader.http import HttpFD
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import DownloadError, ISO639Utils, parse_m3u8_attributes

from .media_transport import TransferState, VerifiedRH
from .media_captions import MAX_CAPTION_BYTES
from .resolution_transport import ResolutionError
from .transfer_progress import TransferProgress, progress_counters  # noqa: F401 -- compatibility import

MAX_MASTER_BYTES = 1024 * 1024
MAX_FILMO_INPUTS = 16
MAX_HLS_CAPTION_SEGMENTS = 4096


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
        self._caption_output_bytes = 0
        self._caption_output_limit = None
        if info_dict.get("ext") == "vtt":
            self._caption_output_limit = 2 * 1024**2
            segments = sum(
                bool(line.strip()) and not line.strip().startswith("#")
                for line in manifest.splitlines()
            )
            if not 1 <= segments <= MAX_HLS_CAPTION_SEGMENTS:
                raise ResolutionError("unsupported_media_tracks")
        # Supplying the same verified manifest keeps the inherited implementation
        # on its native path. Its ffmpeg fallback conditions were rejected above.
        return super().real_download(
            filename,
            {**info_dict, "url": source_url, "hls_media_playlist_data": manifest},
        )

    def _append_fragment(self, ctx, frag_content):
        if self._caption_output_limit is not None:
            self._caption_output_bytes += len(frag_content)
            if self._caption_output_bytes > self._caption_output_limit:
                raise ResolutionError("unsupported_media_tracks")
        return super()._append_fragment(ctx, frag_content)


class SilentLog:
    def debug(self, message):
        pass

    info = warning = error = debug


def transfer(
    url: str,
    directory: Path,
    progress,
    *,
    bandwidth: int | None = None,
    selection: dict | None = None,
    captions=(),
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
    track_records = []
    captions = tuple(captions)
    if selection is None and captions:
        raise ResolutionError("unsupported_media_tracks")
    try:
        with ControlledYDL(state, params) as ydl:
            with ydl.urlopen(url) as response:
                beginning = response.read(512)
                master_url = response.url
            if beginning.lstrip().startswith(b"#EXTM3U"):
                if selection is not None:
                    with ydl.urlopen(master_url) as response:
                        manifest_bytes = response.read(MAX_MASTER_BYTES + 1)
                        master_url = response.url
                    if len(manifest_bytes) > MAX_MASTER_BYTES:
                        raise ResolutionError("unsupported_media_tracks")
                    try:
                        manifest = manifest_bytes.decode("utf-8", errors="strict")
                    except UnicodeDecodeError:
                        raise ResolutionError("extraction_error") from None
                extractor = InfoExtractor(ydl)
                formats, subtitles = extractor._extract_m3u8_formats_and_subtitles(
                    master_url if selection is not None else url,
                    "local",
                    ext="mp4",
                    entry_protocol="m3u8_native",
                )
                videos = [item for item in formats if item.get("vcodec") != "none"]
                if not videos:
                    raise ResolutionError("extraction_error")
                if selection is None:
                    # Keep the established behavior exactly for legacy
                    # providers, whose metadata cannot declare audio tags.
                    video = max(
                        videos,
                        key=lambda item: (
                            item.get("height") or 0,
                            item.get("tbr") or 0,
                        ),
                    )
                    selected = [video]
                    audio = [item for item in formats if item.get("vcodec") == "none"]
                    if video.get("acodec") == "none":
                        if not audio:
                            raise ResolutionError("extraction_error")
                        selected.append(
                            max(audio, key=lambda item: item.get("tbr") or 0)
                        )
                    selected_kinds = ["video"] + (
                        ["audio"] if len(selected) > 1 else []
                    )
                else:
                    if (
                        "#EXT-X-TARGETDURATION" in manifest
                        and "#EXT-X-STREAM-INF:" not in manifest
                    ):
                        if "#EXT-X-ENDLIST" not in manifest:
                            raise ResolutionError("unsupported_media_tracks")
                        expected_audio = selection.get("audio_languages")
                        if (
                            not isinstance(expected_audio, list)
                            or len(expected_audio) != 1
                        ):
                            raise ResolutionError("unsupported_media_tracks")
                        _require_soft_captions(
                            selection,
                            _caption_languages(captions),
                            actual_languages=set(),
                        )
                        video, audio_items, subtitle_items = videos[0], [], []
                    else:
                        video, audio_items, subtitle_items = _select_filmo_hls(
                            manifest,
                            master_url,
                            formats,
                            subtitles,
                            selection,
                            _caption_languages(captions),
                        )
                    selected = [video, *audio_items, *subtitle_items]
                    selected_kinds = [
                        "video",
                        *(["audio"] * len(audio_items)),
                        *(["subtitle"] * len(subtitle_items)),
                    ]
            else:
                selected = [{"url": url, "protocol": "https", "ext": "bin"}]
                selected_kinds = ["video"]
            base_track_count = len(selected)
            if (
                selection is not None
                and not 1 <= base_track_count + len(captions) <= MAX_FILMO_INPUTS
            ):
                raise ResolutionError("unsupported_media_tracks")
            tracker = TransferProgress(
                [
                    *selected,
                    *({"url": "", "ext": caption.format} for caption in captions),
                ]
            )
            # Resolve the small, bounded caption transfers first. Otherwise an
            # unknown future caption size hides byte progress for the video.
            caption_files = ()
            if selection is not None and captions:
                from .media_captions import acquire_captions

                caption_index = [base_track_count]

                def caption_progress(values):
                    progress(tracker.update(caption_index[0], values))
                    if values.get("status") == "finished":
                        caption_index[0] += 1

                caption_files = acquire_captions(
                    captions,
                    ydl,
                    state,
                    directory,
                    caption_progress,
                )
            for number, item in enumerate(selected):
                if item.get("protocol") is None:
                    item["protocol"] = "https"
                allowed_protocols = (
                    ("https", "m3u8_native")
                    if selection is None
                    else ("https", "http", "m3u8_native")
                )
                if item.get("protocol") not in allowed_protocols:
                    raise ResolutionError("extraction_error")
                kind = selected_kinds[number]
                extension = item.get("ext") if kind == "subtitle" else "partial-media"
                if extension not in ("srt", "vtt"):
                    extension = "partial-media"
                output = directory / f"track-{number}.{extension}"
                downloader = (
                    NativeVod if item["protocol"] == "m3u8_native" else HttpFD
                )(ydl, params)

                def update(values, index=number):
                    if values.get("status") in ("downloading", "finished"):
                        if (
                            kind == "subtitle"
                            and values.get("downloaded_bytes", 0) > MAX_CAPTION_BYTES
                        ):
                            raise ResolutionError("unsupported_media_tracks")
                        progress(tracker.update(index, values))

                downloader.add_progress_hook(update)
                success, _ = downloader.download(
                    str(output), {**item, "id": "local", "title": "local"}
                )
                if success is None and kind == "subtitle" and extension == "vtt":
                    # yt-dlp's maintained HLS VTT packer writes the finalized
                    # file but currently returns None on its WebVTT branch.
                    from .media_captions import validate_caption_text

                    if (
                        not output.is_file()
                        or output.stat().st_size > MAX_CAPTION_BYTES
                    ):
                        raise ResolutionError("unsupported_media_tracks")
                    normalized = validate_caption_text(output.read_bytes(), "vtt")
                    output.write_text(normalized, encoding="utf-8", newline="\n")
                    success = True
                if (
                    success is not True
                    or not output.is_file()
                    or not output.stat().st_size
                ):
                    raise ResolutionError(state.error or "extraction_error")
                progress(tracker.finish(number, output.stat().st_size))
                outputs.append(output)
                if selection is not None:
                    language = (
                        _iso639_3(item.get("language"))
                        if kind in ("audio", "subtitle")
                        else None
                    )
                    track_records.append(
                        {
                            "file": output.name,
                            "kind": kind,
                            "language": language,
                            "format": extension if kind == "subtitle" else None,
                        }
                    )
            if caption_files:
                # Acquisition reports wire bytes. Normalizing CRLF/BOM changes
                # the local size, so do not replace those transfer counters.
                for caption in caption_files:
                    outputs.append(caption.path)
                    track_records.append(
                        {
                            "file": caption.path.name,
                            "kind": "subtitle",
                            "language": caption.language,
                            "format": caption.format,
                        }
                    )
            if selection is not None:
                _write_tracks(directory, track_records)
        return outputs
    except DownloadError:
        raise ResolutionError(state.error or "extraction_error") from None


def _iso639_3(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    tag = value.strip().replace("_", "-").split("-", 1)[0].lower()
    from catalog_core.providers.filmo import LANGUAGES

    if tag in LANGUAGES:
        return LANGUAGES[tag]
    if len(tag) == 3 and tag.isalpha():
        return tag
    if len(tag) == 2 and tag.isalpha():
        try:
            return ISO639Utils.short2long(tag)
        except KeyError:
            return None
    return None


def _parse_master_groups(
    manifest: str, master_url: str
) -> tuple[list[dict], list[dict], list[dict]]:
    audio, captions = [], []
    streams = []
    pending_stream = None
    for line in manifest.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-MEDIA:"):
            attributes = parse_m3u8_attributes(line)
            kind = attributes.get("TYPE")
            if kind in {"AUDIO", "SUBTITLES"}:
                uri = attributes.get("URI")
                record = {
                    "group": attributes.get("GROUP-ID"),
                    "language": _iso639_3(attributes.get("LANGUAGE")),
                    "url": urljoin(master_url, uri) if uri else None,
                    "name": attributes.get("NAME"),
                }
                (audio if kind == "AUDIO" else captions).append(record)
        elif line.startswith("#EXT-X-STREAM-INF:"):
            pending_stream = parse_m3u8_attributes(line)
        elif line and not line.startswith("#") and pending_stream is not None:
            streams.append(
                {
                    "url": urljoin(master_url, line),
                    "audio_group": pending_stream.get("AUDIO"),
                    "subtitle_group": pending_stream.get("SUBTITLES"),
                }
            )
            pending_stream = None
    return streams, audio, captions


def _caption_languages(captions) -> set[str]:
    from .media_captions import normalize_caption_language

    return {
        language
        for caption in captions
        if (language := normalize_caption_language(getattr(caption, "language", None)))
    }


def _require_soft_captions(selection, provided, *, actual_languages):
    if selection.get("subtitle_mode") != "soft":
        return
    expected = selection.get("subtitle_languages")
    if not isinstance(expected, list):
        raise ResolutionError("unsupported_media_tracks")
    if any(language in ("und", "mul") for language in expected):
        raise ResolutionError("unsupported_media_tracks")
    if not set(expected).issubset(provided | actual_languages):
        raise ResolutionError("unsupported_media_tracks")


def _unique_by_url(items: list[dict], url: str) -> dict:
    found = [item for item in items if item.get("url") == url]
    if len(found) != 1:
        raise ResolutionError("unsupported_media_tracks")
    return found[0]


def _select_filmo_hls(
    manifest, master_url, formats, subtitles, selection, provided_caption_languages
):
    streams, audio_rows, subtitle_rows = _parse_master_groups(manifest, master_url)
    candidates = []
    for video in formats:
        if video.get("vcodec") == "none" or not video.get("url"):
            continue
        rows = [row for row in streams if row["url"] == video["url"]]
        if len(rows) != 1:
            continue
        candidates.append((video, rows[0]))
    if not candidates:
        raise ResolutionError("unsupported_media_tracks")

    expected_audio = selection.get("audio_languages")
    if (
        not isinstance(expected_audio, list)
        or not 1 <= len(expected_audio) <= 8
        or any(
            not isinstance(language, str) or language in ("und", "mul")
            for language in expected_audio
        )
        or len(set(expected_audio)) != len(expected_audio)
    ):
        raise ResolutionError("unsupported_media_tracks")

    expected_subtitles = selection.get("subtitle_languages")
    if expected_subtitles is not None and (
        not isinstance(expected_subtitles, list)
        or len(expected_subtitles) > 8
        or any(not isinstance(language, str) for language in expected_subtitles)
        or len(set(expected_subtitles)) != len(expected_subtitles)
    ):
        raise ResolutionError("unsupported_media_tracks")

    compatible = []
    audio_formats = [item for item in formats if item.get("vcodec") == "none"]
    for video, stream in candidates:
        group_id = stream["audio_group"]
        if group_id:
            group_rows = [row for row in audio_rows if row["group"] == group_id]
            if not group_rows:
                continue
            selected_audio = []
            valid = True
            for language in expected_audio:
                rows = [row for row in group_rows if row["language"] == language]
                if len(rows) != 1:
                    valid = False
                    break
                row = rows[0]
                if not row["url"]:
                    valid = False
                    break
                try:
                    audio = _unique_by_url(audio_formats, row["url"])
                except ResolutionError:
                    valid = False
                    break
                selected_audio.append(({**audio, "language": language}, language))
            if not valid:
                continue
        elif (
            isinstance(video.get("acodec"), str)
            and video.get("acodec") != "none"
            and len(expected_audio) == 1
        ):
            # Preserve an already multiplexed source as-is. We never rewrite
            # its language metadata from a catalogue declaration.
            selected_audio = []
        else:
            continue

        caption_group = stream["subtitle_group"]
        selected_subtitles = []
        if expected_subtitles != [] and caption_group:
            caption_rows = [
                row for row in subtitle_rows if row["group"] == caption_group
            ]
            parsed_captions = [
                item
                for items in subtitles.values()
                for item in items
                if isinstance(item, dict)
            ]
            captions_valid = True
            for row in caption_rows:
                language = row["language"]
                if language is None or not row["url"]:
                    captions_valid = False
                    break
                try:
                    caption = _unique_by_url(parsed_captions, row["url"])
                except ResolutionError:
                    captions_valid = False
                    break
                ext = caption.get("ext")
                protocol = caption.get("protocol", "https")
                if ext not in ("srt", "vtt") or protocol not in (
                    "https",
                    "http",
                    "m3u8_native",
                ):
                    captions_valid = False
                    break
                selected_subtitles.append(({**caption, "language": language}, language))
            if not captions_valid:
                continue
        actual_languages = {language for _, language in selected_subtitles}
        try:
            _require_soft_captions(
                selection,
                provided_caption_languages,
                actual_languages=actual_languages,
            )
        except ResolutionError:
            continue
        compatible.append((video, selected_audio, selected_subtitles))

    if not compatible:
        raise ResolutionError("unsupported_media_tracks")
    compatible.sort(
        key=lambda entry: (
            entry[0].get("height") or 0,
            entry[0].get("tbr") or 0,
        ),
        reverse=True,
    )
    if len(compatible) > 1 and (
        (compatible[0][0].get("height") or 0, compatible[0][0].get("tbr") or 0)
        == (compatible[1][0].get("height") or 0, compatible[1][0].get("tbr") or 0)
    ):
        raise ResolutionError("unsupported_media_tracks")
    video, selected_audio, selected_subtitles = compatible[0]
    # Keep audio after video and captions after audio. Sidecar records follow
    # this same order and are checked against the child result before remux.
    return (
        video,
        [item for item, _ in selected_audio],
        [item for item, _ in selected_subtitles],
    )


def _write_tracks(directory: Path, records: list[dict]) -> None:
    if not 1 <= len(records) <= MAX_FILMO_INPUTS:
        raise ResolutionError("unsupported_media_tracks")
    if (
        records[0].get("kind") != "video"
        or sum(item.get("kind") == "video" for item in records) != 1
        or sum(item.get("kind") == "audio" for item in records) > 8
        or sum(item.get("kind") == "subtitle" for item in records) > 8
    ):
        raise ResolutionError("unsupported_media_tracks")
    body = json.dumps({"version": 1, "tracks": records}, separators=(",", ":")).encode()
    if len(body) > 8192:
        raise ResolutionError("unsupported_media_tracks")
    path = directory / "tracks.json"
    with path.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
