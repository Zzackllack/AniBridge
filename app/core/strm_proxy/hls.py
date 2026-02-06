from __future__ import annotations

import re
from typing import Callable
from urllib.parse import urljoin

from loguru import logger

_URI_TAG_PREFIXES = (
    "#EXT-X-KEY",
    "#EXT-X-MAP",
    "#EXT-X-MEDIA",
    "#EXT-X-I-FRAME-STREAM-INF",
    "#EXT-X-SESSION-KEY",
    "#EXT-X-PRELOAD-HINT",
    "#EXT-X-RENDITION-REPORT",
    "#EXT-X-SESSION-DATA",
)

_URI_ATTR_RE = re.compile(r'URI=(?:"(?P<uri_quoted>[^"]*)"|(?P<uri_unquoted>[^,]*))')
_STREAM_INF_PREFIX = "#EXT-X-STREAM-INF:"
_EXTINF_PREFIX = "#EXTINF:"
_MIN_AVERAGE_BANDWIDTH = 192_000


def _split_hls_attrs(raw: str) -> list[str]:
    """
    Split an HLS attribute list by commas while respecting quoted values.
    """
    parts: list[str] = []
    buf: list[str] = []
    in_quotes = False
    for ch in raw:
        if ch == '"':
            in_quotes = not in_quotes
        if ch == "," and not in_quotes:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_bandwidth(attrs: list[str]) -> int | None:
    """
    Return parsed BANDWIDTH from `#EXT-X-STREAM-INF` attributes when present.
    """
    for attr in attrs:
        if "=" not in attr:
            continue
        key, value = attr.split("=", 1)
        if key.strip().upper() != "BANDWIDTH":
            continue
        try:
            return int(value.strip().strip('"'))
        except ValueError:
            return None
    return None


def _compute_average_bandwidth(bandwidth: int) -> int:
    """
    Compute a conservative AVERAGE-BANDWIDTH estimate from BANDWIDTH.
    """
    return max(int(bandwidth * 0.85), _MIN_AVERAGE_BANDWIDTH)


def is_hls_media_playlist(playlist_text: str) -> bool:
    """
    Return whether playlist text looks like a media playlist (not master).
    """
    if not playlist_text:
        return False
    has_stream_inf = False
    has_extinf = False
    for raw_line in playlist_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(_STREAM_INF_PREFIX):
            has_stream_inf = True
        if line.startswith(_EXTINF_PREFIX):
            has_extinf = True
    return has_extinf and not has_stream_inf


def inject_stream_inf_bandwidth_hints(
    playlist_text: str, *, default_bandwidth: int
) -> str:
    """
    Ensure master playlist variants include BANDWIDTH and AVERAGE-BANDWIDTH.
    """
    if not playlist_text:
        return playlist_text
    if default_bandwidth <= 0:
        default_bandwidth = _MIN_AVERAGE_BANDWIDTH

    ends_with_newline = playlist_text.endswith("\n")
    out_lines: list[str] = []
    for line in playlist_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(_STREAM_INF_PREFIX):
            out_lines.append(line)
            continue

        prefix_idx = line.find(_STREAM_INF_PREFIX)
        prefix = line[:prefix_idx] + _STREAM_INF_PREFIX
        attrs_raw = line[prefix_idx + len(_STREAM_INF_PREFIX) :]
        attrs = _split_hls_attrs(attrs_raw)
        keys = {
            attr.split("=", 1)[0].strip().upper()
            for attr in attrs
            if "=" in attr and attr.split("=", 1)[0].strip()
        }
        bandwidth = _parse_bandwidth(attrs)
        if "BANDWIDTH" not in keys:
            bandwidth = default_bandwidth
            attrs.append(f"BANDWIDTH={bandwidth}")
        if bandwidth is None:
            bandwidth = default_bandwidth
        if "AVERAGE-BANDWIDTH" not in keys:
            attrs.append(f"AVERAGE-BANDWIDTH={_compute_average_bandwidth(bandwidth)}")
        out_lines.append(prefix + ",".join(attrs))

    result = "\n".join(out_lines)
    if ends_with_newline:
        result += "\n"
    return result


def build_synthetic_master_playlist(media_playlist_url: str, *, bandwidth: int) -> str:
    """
    Build a minimal master playlist that points to a media playlist URL.
    """
    if bandwidth <= 0:
        bandwidth = _MIN_AVERAGE_BANDWIDTH
    average = _compute_average_bandwidth(bandwidth)
    return (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},AVERAGE-BANDWIDTH={average}\n"
        f"{media_playlist_url}\n"
    )


def _rewrite_uri_attr(
    line: str, base_url: str, rewrite_url: Callable[[str], str]
) -> str:
    """
    Rewrite URI attributes found in a single HLS tag line.

    Parameters:
        line (str): An HLS tag line that may contain one or more `URI=...` attributes.
        base_url (str): Base URL used to resolve any relative URIs found in the line.
        rewrite_url (Callable[[str], str]): Function that takes an absolute URI and returns its rewritten (proxied) form.

    Returns:
        str: The input line with each `URI` attribute replaced by its resolved and rewritten URI, preserving whether the original attribute used quotes.
    """
    logger.trace("Rewriting HLS tag URI in line: {}", line.strip())

    def _replace(match: re.Match[str]) -> str:
        """
        Replace a regex match for an HLS URI attribute with a rewritten absolute/proxied URI, preserving original quoting.

        Parameters:
                match (re.Match[str]): A regex match object with named groups "uri_quoted" (the URI inside quotes) and
                    "uri_unquoted" (the URI without quotes).

        Returns:
                str: The replacement attribute string in the form `URI="proxied"` if the original used quotes, or
                    `URI=proxied` if the original was unquoted.
        """
        raw_uri = match.group("uri_quoted") or match.group("uri_unquoted") or ""
        abs_uri = urljoin(base_url, raw_uri)
        proxied = rewrite_url(abs_uri)
        if match.group("uri_quoted") is not None:
            return f'URI="{proxied}"'
        return f"URI={proxied}"

    return _URI_ATTR_RE.sub(_replace, line)


def rewrite_hls_playlist(
    playlist_text: str, *, base_url: str, rewrite_url: Callable[[str], str]
) -> str:
    """
    Rewrite every URI in an HLS playlist using a base URL to resolve relative references and a provided URL-rewriting function.

    Preserves non-URI lines, tag formatting, and the original trailing newline (if any).

    Parameters:
        playlist_text (str): The raw HLS playlist text to rewrite.
        base_url (str): Base URL used to resolve relative URIs in the playlist.
        rewrite_url (Callable[[str], str]): Callable that receives an absolute URI and returns the rewritten/proxied URI.

    Returns:
        str: The playlist text with all URI-bearing tags and standalone URI lines rewritten; preserves the original trailing newline when present.
    """
    logger.debug("Rewriting HLS playlist from {}", base_url)
    if not playlist_text:
        return playlist_text

    ends_with_newline = playlist_text.endswith("\n")
    lines = playlist_text.splitlines()
    out_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        if stripped.startswith("#"):
            if stripped.startswith(_URI_TAG_PREFIXES):
                out_lines.append(_rewrite_uri_attr(line, base_url, rewrite_url))
            else:
                out_lines.append(line)
            continue

        abs_uri = urljoin(base_url, stripped)
        logger.trace("Rewriting HLS URI line: {}", stripped)
        out_lines.append(rewrite_url(abs_uri))

    result = "\n".join(out_lines)
    if ends_with_newline:
        result += "\n"
    logger.debug("Rewrote HLS playlist ({} lines)", len(out_lines))
    return result
