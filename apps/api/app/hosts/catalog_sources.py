"""Pure maintained host parsing for the supervised snapshot resolver.

Network helpers in the upstream modules are deliberately excluded: they bypass
our shared request budget, and Doodstream's helper disables TLS verification.
"""

import json
import re
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidTag

from app.utils.aniworld_compat import prepare_aniworld_home

# Other host modules are upstream stubs or require delivery headers which the
# current URL-only receipt cannot represent. Keep their capability explicit.
SUPPORTED = frozenset({"VOE", "Byse", "Filemoon", "Vidoza"})


class UnsupportedMediaTracks(ValueError):
    """Playback advertises tracks that the current transfer path cannot retain."""


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
    prepare_aniworld_home()
    from aniworld.extractors.provider.filemoon import _extract_file_code

    code = _extract_file_code(embed_url)
    if code is None:
        return None
    parsed = urlsplit(embed_url)
    return f"{parsed.scheme}://{parsed.netloc}/api/videos/{code}"


def byse_api(embed_url: str) -> str | None:
    """Return the API endpoint only for the observed HTTPS Byse embed shape."""
    parsed = urlsplit(embed_url)
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or re.fullmatch(r"byse[a-z0-9-]*\.[a-z]{2,}", parsed.hostname or "") is None
        or (match := re.fullmatch(r"/[de]/([A-Za-z0-9]{6,64})", parsed.path)) is None
    ):
        return None
    return f"{parsed.scheme}://{parsed.netloc}/api/videos/{match[1]}"


def filemoon_source(body: str, *, reject_external_tracks: bool = False) -> str | None:
    """Decode observed playback data without claiming its height as quality."""
    prepare_aniworld_home()
    from aniworld.extractors.provider.filemoon import (
        _decrypt_playback_data,
        _extract_best_source_url,
    )

    try:
        value = json.loads(body)
        playback = value.get("playback") if isinstance(value, dict) else None
        if not isinstance(playback, dict):
            return None
        if reject_external_tracks:
            _reject_unsupported_tracks(value)
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
            value = playback.get(name)
            if value is not None and (
                not isinstance(value, str)
                or len(value) > (128 if name.startswith("iv") else 16 * 1024**2)
            ):
                return None
        data = _decrypt_playback_data(playback)
        if not isinstance(data, dict):
            return None
        if reject_external_tracks:
            _reject_unsupported_tracks(data)
        sources = data.get("sources")
        if sources is not None and (
            not isinstance(sources, list)
            or len(sources) > 100
            or not all(isinstance(source, dict) for source in sources)
        ):
            return None
        source = _extract_best_source_url(data)
        return source if isinstance(source, str) else None
    except UnsupportedMediaTracks:
        raise
    except ValueError, TypeError, InvalidTag:
        return None
