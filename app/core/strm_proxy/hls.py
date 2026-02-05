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
    Rewrite URI attributes found in a single HLS tag line.

    Parameters:
        line (str): An HLS tag line that may contain one or more `URI=...` attributes.
        base_url (str): Base URL used to resolve any relative URIs found in the line.
        rewrite_url (Callable[[str], str]): Function that takes an absolute URI and returns its rewritten (proxied) form.

    Returns:
        str: The input line with each `URI` attribute replaced by its resolved and rewritten URI, preserving whether the original attribute used quotes.
    """
    from loguru import logger

    logger.trace("Rewriting HLS tag URI in line: {}", line.strip())

    def _replace(match: re.Match[str]) -> str:
        """
        Replace a regex match for an HLS URI attribute with a rewritten absolute/proxied URI, preserving original quoting.

        Parameters:
                match (re.Match[str]): A regex match object with named groups "uri" (the original URI text, possibly relative) and "quote" (the surrounding quote character if present).

        Returns:
                str: The replacement attribute string in the form `URI="proxied"` if the original used quotes, or `URI=proxied` otherwise.
        """
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
    Rewrite every URI in an HLS playlist using a base URL to resolve relative references and a provided URL-rewriting function.

    Preserves non-URI lines, tag formatting, and the original trailing newline (if any).

    Parameters:
        playlist_text (str): The raw HLS playlist text to rewrite.
        base_url (str): Base URL used to resolve relative URIs in the playlist.
        rewrite_url (Callable[[str], str]): Callable that receives an absolute URI and returns the rewritten/proxied URI.

    Returns:
        str: The playlist text with all URI-bearing tags and standalone URI lines rewritten; preserves the original trailing newline when present.
    """
    from loguru import logger

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
    logger.success("Rewrote HLS playlist ({} lines)", len(out_lines))
    return result
