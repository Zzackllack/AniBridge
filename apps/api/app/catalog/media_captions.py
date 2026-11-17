"""Private Byse caption descriptors and bounded verified acquisition."""

from __future__ import annotations

import re
import secrets
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeAlias

from catalog_core.providers.filmo import LANGUAGES
from yt_dlp.utils import ISO639Utils

from .resolution_transport import ResolutionError

if TYPE_CHECKING:
    from .media_download import ControlledYDL
    from .media_transport import TransferState

CaptionFormat = Literal["srt", "vtt"]
MAX_CAPTION_TRACKS = 8
MAX_CAPTION_BYTES = 2 * 1024**2
READ_CHUNK_BYTES = 64 * 1024
ProgressRecord: TypeAlias = dict[str, str | int | None]
ProgressCallback: TypeAlias = Callable[[ProgressRecord], None]

_LANGUAGE_NAMES = {
    "de": "deu",
    "deutsch": "deu",
    "german": "deu",
    "en": "eng",
    "english": "eng",
    "englisch": "eng",
    "ja": "jpn",
    "japanese": "jpn",
    "japanisch": "jpn",
    "it": "ita",
    "italian": "ita",
    "italiano": "ita",
    "italienisch": "ita",
    "es": "spa",
    "spanish": "spa",
    "español": "spa",
    "spanisch": "spa",
    "fr": "fra",
    "french": "fra",
    "français": "fra",
    "französisch": "fra",
}
_TIMESTAMP = re.compile(
    r"(?m)^(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{3}\s+-->\s+"
    r"(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{3}(?:\s+.*)?$"
)


@dataclass(frozen=True)
class CaptionTrack:
    """Ephemeral upstream URL plus explicit track semantics."""

    url: str = field(repr=False)
    language: str
    format: CaptionFormat


@dataclass(frozen=True)
class CaptionFile:
    """Validated local caption input for the supervised remux stage."""

    path: Path
    language: str
    format: CaptionFormat


def normalize_caption_language(value: object) -> str | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return None
    key = " ".join(value.strip().casefold().split())
    key = re.split(r"[-_]", key, maxsplit=1)[0]
    language = _LANGUAGE_NAMES.get(key) or LANGUAGES.get(key)
    if language == "und":
        return None
    if language is None and len(key) == 2 and key.isalpha():
        try:
            language = ISO639Utils.short2long(key)
        except KeyError:
            return None
    if language is None and len(key) == 3 and key.isalpha():
        # The maintained table maps both ISO 639-2 aliases and 639-3 codes to
        # a two-letter code. Convert back so stream metadata stays ISO 639-3.
        short = ISO639Utils.long2short(key)
        if short:
            language = ISO639Utils.short2long(short)
    return language


def validate_caption_text(body: bytes, format: CaptionFormat) -> str:
    if not body or len(body) > MAX_CAPTION_BYTES or b"\x00" in body:
        raise ResolutionError("unsupported_media_tracks")
    try:
        text = body.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ResolutionError("unsupported_media_tracks") from None
    if any(ord(char) < 32 and char not in "\r\n\t" for char in text):
        raise ResolutionError("unsupported_media_tracks")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if format == "vtt":
        if not normalized.startswith("WEBVTT") or not _TIMESTAMP.search(normalized):
            raise ResolutionError("unsupported_media_tracks")
    elif format == "srt":
        if not _TIMESTAMP.search(normalized):
            raise ResolutionError("unsupported_media_tracks")
    else:
        raise ResolutionError("unsupported_media_tracks")
    return normalized


def acquire_captions(
    captions: tuple[CaptionTrack, ...],
    ydl: ControlledYDL,
    state: TransferState,
    directory: Path,
    progress: ProgressCallback | None = None,
) -> tuple[CaptionFile, ...]:
    """Download known captions through the caller's verified yt-dlp handler.

    The supplied ``ydl`` owns DNS pinning, TLS, redirect limits, and timeouts.
    Caption files use generated names; provider URLs and filenames never enter
    the local receipt or transfer sidecar.
    """
    if not captions:
        return ()
    if len(captions) > MAX_CAPTION_TRACKS:
        raise ResolutionError("unsupported_media_tracks")
    directory.mkdir(parents=True, exist_ok=True)
    completed: list[CaptionFile] = []
    created: list[Path] = []
    succeeded = False
    try:
        for index, track in enumerate(captions):
            if (
                not isinstance(track, CaptionTrack)
                or normalize_caption_language(track.language) != track.language
                or track.format not in ("srt", "vtt")
            ):
                raise ResolutionError("unsupported_media_tracks")
            token = secrets.token_hex(8)
            temporary = directory / f"caption-{index}-{token}.partial-caption"
            output = directory / f"caption-{index}-{token}.{track.format}"
            received = bytearray()
            with ydl.urlopen(track.url) as response:
                content_length = response.headers.get("Content-Length")
                expected_bytes = None
                if content_length is not None:
                    if not content_length.isascii() or not content_length.isdecimal():
                        raise ResolutionError("unsupported_media_tracks")
                    if int(content_length) > MAX_CAPTION_BYTES:
                        raise ResolutionError("unsupported_media_tracks")
                    expected_bytes = int(content_length)
                with temporary.open("xb") as stream:
                    created.append(temporary)
                    while True:
                        if shutil.disk_usage(directory).free < 512 * 1024**2:
                            state.fail("storage_full")
                        chunk = response.read(
                            min(READ_CHUNK_BYTES, MAX_CAPTION_BYTES + 1 - len(received))
                        )
                        if not chunk:
                            break
                        received.extend(chunk)
                        if len(received) > MAX_CAPTION_BYTES:
                            raise ResolutionError("unsupported_media_tracks")
                        stream.write(chunk)
                        if progress is not None:
                            progress(
                                {
                                    "status": "downloading",
                                    "downloaded_bytes": len(received),
                                    "total_bytes": int(content_length)
                                    if content_length
                                    else None,
                                    "speed": None,
                                    "eta": None,
                                }
                            )
            if expected_bytes is not None and len(received) != expected_bytes:
                raise ResolutionError("transport_failure")
            text = validate_caption_text(bytes(received), track.format)
            temporary.write_text(text, encoding="utf-8", newline="\n")
            temporary.replace(output)
            created.remove(temporary)
            created.append(output)
            completed.append(CaptionFile(output, track.language, track.format))
            if progress is not None:
                progress(
                    {
                        "status": "finished",
                        "downloaded_bytes": len(received),
                        "total_bytes": len(received),
                        "speed": 0,
                        "eta": 0,
                    }
                )
        succeeded = True
        return tuple(completed)
    except ResolutionError:
        raise
    except Exception:  # noqa: BLE001 -- upstream transport messages may contain URLs
        code = getattr(state, "error", None) or "transport_failure"
        raise ResolutionError(code) from None
    finally:
        keep = {item.path for item in completed} if succeeded else set()
        for path in created:
            if path not in keep:
                path.unlink(missing_ok=True)
