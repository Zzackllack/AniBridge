"""Pure maintained host parsing for the supervised snapshot resolver.

Network helpers in the upstream modules are deliberately excluded: they bypass
our shared request budget, and Doodstream's helper disables TLS verification.
"""

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidTag

from app.utils.aniworld_compat import prepare_aniworld_home
from app.catalog.media_captions import (
    MAX_CAPTION_TRACKS,
    CaptionTrack,
    normalize_caption_language,
)

# Other host modules are upstream stubs or require delivery headers which the
# current URL-only receipt cannot represent. Keep their capability explicit.
SUPPORTED = frozenset({"VOE", "Byse", "Filemoon", "Vidoza"})


class UnsupportedMediaTracks(ValueError):
    """Playback advertises tracks that the current transfer path cannot retain."""


@dataclass(frozen=True)
class BysePlayback:
    source_url: str = field(repr=False)
    captions: tuple[CaptionTrack, ...] = ()


def _thumbnail_only_tracks(value: object) -> bool:
    if not isinstance(value, list) or len(value) > 64:
        return False
    for track in value:
        if not isinstance(track, dict):
            return False
        kinds = [track[key] for key in ("kind", "type") if key in track]
        if (
            not kinds
            or any(not isinstance(kind, str) for kind in kinds)
            or {kind.strip().casefold() for kind in kinds}
            not in ({"thumbnail"}, {"thumbnails"})
            or set(track) - {"kind", "type", "file", "url", "src"}
            or not any(
                isinstance(track.get(field), str) and track[field]
                for field in ("file", "url", "src")
            )
        ):
            return False
    return True


def _reject_unsupported_tracks(value: dict) -> None:
    for name, tracks in value.items():
        normalized = (
            re.sub(r"[_-]", "", name.casefold()) if isinstance(name, str) else ""
        )
        if not any(marker in normalized for marker in ("track", "caption", "subtitle")):
            continue
        if normalized == "tracks" and _thumbnail_only_tracks(tracks):
            continue
        if normalized != "tracks" and tracks == []:
            continue
        raise UnsupportedMediaTracks("Byse API advertises unsupported track metadata")


def _known_caption_tracks(value: dict) -> tuple[CaptionTrack, ...]:
    found: list[CaptionTrack] = []
    for name, rows in value.items():
        normalized = (
            re.sub(r"[_-]", "", name.casefold()) if isinstance(name, str) else ""
        )
        if not any(marker in normalized for marker in ("track", "caption", "subtitle")):
            continue
        if normalized != "tracks" or not isinstance(rows, list) or len(rows) > 64:
            if normalized != "tracks" and rows == []:
                continue
            raise UnsupportedMediaTracks(
                "Byse API advertises unsupported track metadata"
            )
        for row in rows:
            # Sprites share the track list but are not subtitle inputs.
            if _thumbnail_only_tracks([row]):
                continue
            if not isinstance(row, dict):
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            kinds = [row[key] for key in ("kind", "type") if key in row]
            canonical_kinds = {
                "caption"
                if kind.casefold().strip() in {"caption", "captions"}
                else "subtitle"
                if kind.casefold().strip() in {"subtitle", "subtitles"}
                else "unknown"
                for kind in kinds
                if isinstance(kind, str)
            }
            if (
                not kinds
                or len(canonical_kinds) != 1
                or "unknown" in canonical_kinds
                or len(kinds) != sum(isinstance(kind, str) for kind in kinds)
                or set(row)
                - {
                    "kind",
                    "type",
                    "file",
                    "url",
                    "src",
                    "label",
                    "language",
                    "lang",
                    "srclang",
                    "format",
                    "mime",
                    "default",
                }
            ):
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )

            targets = [row[key] for key in ("file", "url", "src") if key in row]
            explicit_language_values = [
                row[key] for key in ("language", "lang", "srclang") if key in row
            ]
            if (
                len(targets) != 1
                or not isinstance(targets[0], str)
                or any(not isinstance(item, str) for item in explicit_language_values)
                or ("label" in row and not isinstance(row["label"], str))
                or ("default" in row and type(row["default"]) is not bool)
            ):
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            explicit_languages = [
                normalize_caption_language(item) for item in explicit_language_values
            ]
            if any(language is None for language in explicit_languages):
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            if len(set(explicit_languages)) > 1:
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            explicit_language = explicit_languages[0] if explicit_languages else None
            label_language = (
                normalize_caption_language(row["label"]) if "label" in row else None
            )
            if label_language is None and explicit_language is None:
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            if (
                label_language is not None
                and explicit_language is not None
                and label_language != explicit_language
            ):
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            language = explicit_language or label_language
            url = targets[0]
            try:
                parsed = urlsplit(url)
                encoded_length = len(url.encode())
                port = parsed.port
            except UnicodeError, ValueError:
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                ) from None
            if (
                not 1 <= encoded_length <= 4096
                or parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or port not in (None, 443)
                or parsed.fragment
                or any(ord(char) < 33 for char in url)
            ):
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            formats = [row[key] for key in ("format", "mime") if key in row]
            suffix = parsed.path.rsplit("/", 1)[-1].rsplit(".", 1)
            inferred = suffix[-1].casefold() if len(suffix) == 2 else None
            declared = []
            for format_value in formats:
                if not isinstance(format_value, str):
                    raise UnsupportedMediaTracks(
                        "Byse API advertises unsupported track metadata"
                    )
                item = format_value.strip().casefold()
                declared.append(
                    "vtt"
                    if item in {"vtt", "text/vtt"}
                    else "srt"
                    if item
                    in {"srt", "subrip", "application/x-subrip", "application/srt"}
                    else "unknown"
                )
            if len(set(declared)) > 1 or "unknown" in declared:
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            fmt = declared[0] if declared else inferred
            if fmt not in ("srt", "vtt") or (
                inferred in ("srt", "vtt") and inferred != fmt
            ):
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
            found.append(CaptionTrack(url=url, language=language, format=fmt))
    if len(found) > MAX_CAPTION_TRACKS:
        raise UnsupportedMediaTracks("Byse API advertises unsupported track metadata")
    unique = {(track.url, track.language, track.format): track for track in found}
    if len(unique) != len(found):
        found = list(unique.values())
    return tuple(found)


def html_source(host: str, html: str) -> str | None:
    prepare_aniworld_home()
    if host in {"Filemoon", "Byse"}:
        from aniworld.extractors.provider.filemoon import _try_extract_from_html

        return _try_extract_from_html(html)
    if host == "Vidoza":
        from aniworld.extractors.provider.vidoza import SOURCE_LINK_PATTERN

        match = SOURCE_LINK_PATTERN.search(html) if "sourcesCode:" in html else None
        return match.group(1) if match else None
    return None


def filemoon_api(embed_url: str) -> str | None:
    """Build the observed HTTPS Filemoon/Byse API URL from a recognized embed."""
    try:
        parsed = urlsplit(embed_url)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or not parsed.hostname
    ):
        return None
    prepare_aniworld_home()
    from aniworld.extractors.provider.filemoon import _extract_file_code

    code = _extract_file_code(embed_url)
    if code is None:
        return None
    # Use hostname, not netloc: the netloc may retain mixed case or userinfo.
    return f"{parsed.scheme}://{parsed.hostname}/api/videos/{code}"


def byse_api(embed_url: str) -> str | None:
    """Return the API endpoint only for the observed HTTPS Byse embed shape."""
    try:
        parsed = urlsplit(embed_url)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or re.fullmatch(r"byse[a-z0-9-]*\.[a-z]{2,}", parsed.hostname or "") is None
        or (match := re.fullmatch(r"/[de]/([A-Za-z0-9]{6,64})", parsed.path)) is None
    ):
        return None
    # hostname is normalized/lowercased and cannot include userinfo; netloc may.
    return f"{parsed.scheme}://{parsed.hostname}/api/videos/{match[1]}"


def filemoon_playback(
    body: str,
    *,
    allow_external_captions: bool = False,
    reject_external_tracks: bool = False,
) -> BysePlayback | None:
    """Decode playback and, when opted in, recognized private caption inputs."""
    prepare_aniworld_home()
    from aniworld.extractors.provider.filemoon import (
        _decrypt_playback_data,
        _extract_best_source_url,
    )

    try:
        api_value = json.loads(body)
        playback = api_value.get("playback") if isinstance(api_value, dict) else None
        if not isinstance(playback, dict):
            return None
        if reject_external_tracks:
            _reject_unsupported_tracks(api_value)
            _reject_unsupported_tracks(playback)
        # Versioned Byse responses carry thirty keys, but the installed pure
        # decoder concatenates every 16-byte part. Select the two documented
        # version positions before handing it the reduced envelope.
        version = playback.get("version")
        parts = playback.get("key_parts")
        if not isinstance(parts, list) or not 1 <= len(parts) <= 64:
            return None
        if version is not None:
            # The live API uses a decimal string; older envelopes used numbers.
            if type(version) is str:
                if (
                    len(version) > 16
                    or not version.strip().isascii()
                    or not version.strip().isdecimal()
                ):
                    return None
                version = int(version.strip())
            if type(version) is not int or not 1 <= version <= 20 or len(parts) != 30:
                return None
            parts = [parts[version - 1], parts[30 - version]]
        elif len(parts) > 4:
            return None
        playback = {**playback, "key_parts": parts}
        if not all(isinstance(part, str) and len(part) <= 128 for part in parts):
            return None
        for name in ("iv", "iv2", "payload", "payload2"):
            component = playback.get(name)
            if component is not None and (
                not isinstance(component, str)
                or len(component) > (128 if name.startswith("iv") else 16 * 1024**2)
            ):
                return None
        data = _decrypt_playback_data(playback)
        if not isinstance(data, dict):
            return None
        if allow_external_captions:
            captions = (
                *_known_caption_tracks(api_value),
                *_known_caption_tracks(playback),
                *_known_caption_tracks(data),
            )
            if len(captions) > MAX_CAPTION_TRACKS:
                raise UnsupportedMediaTracks(
                    "Byse API advertises unsupported track metadata"
                )
        elif reject_external_tracks:
            _reject_unsupported_tracks(data)
            captions = ()
        else:
            captions = ()
        sources = data.get("sources")
        if sources is not None and (
            not isinstance(sources, list)
            or len(sources) > 100
            or not all(isinstance(source, dict) for source in sources)
        ):
            return None
        source = _extract_best_source_url(data)
        return BysePlayback(source, captions) if isinstance(source, str) else None
    except UnsupportedMediaTracks:
        raise
    except ValueError, TypeError, InvalidTag:
        return None


def filemoon_source(body: str, *, reject_external_tracks: bool = False) -> str | None:
    """Decode observed playback data without claiming its height as quality."""
    value = filemoon_playback(body, reject_external_tracks=reject_external_tracks)
    return value.source_url if value is not None else None
