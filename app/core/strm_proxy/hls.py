from __future__ import annotations

import re
from typing import Callable
from urllib.parse import urljoin


_URI_TAG_PREFIXES = (
    "#EXT-X-KEY",
    "#EXT-X-MAP",
    "#EXT-X-MEDIA",
    "#EXT-X-I-FRAME-STREAM-INF",
    "#EXT-X-SESSION-KEY",
)

_URI_ATTR_RE = re.compile(r'URI=(?P<quote>"?)(?P<uri>[^",]*)(?P=quote)')


def _rewrite_uri_attr(
    line: str, base_url: str, rewrite_url: Callable[[str], str]
) -> str:
    """
    Rewrite URI attributes within a single HLS tag line.
    """
    def _replace(match: re.Match[str]) -> str:
        raw_uri = match.group("uri")
        abs_uri = urljoin(base_url, raw_uri)
        proxied = rewrite_url(abs_uri)
        quote = match.group("quote") or ""
        if quote:
            return f'URI="{proxied}"'
        return f"URI={proxied}"

    return _URI_ATTR_RE.sub(_replace, line)


def rewrite_hls_playlist(
    playlist_text: str, *, base_url: str, rewrite_url: Callable[[str], str]
) -> str:
    """
    Rewrite all URI-bearing lines/tags in an HLS playlist.
    """
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
        out_lines.append(rewrite_url(abs_uri))

    result = "\n".join(out_lines)
    if ends_with_newline:
        result += "\n"
    return result
