from __future__ import annotations

from typing import Mapping
from urllib.parse import urlencode, urljoin, urlsplit

from app.config import STRM_PUBLIC_BASE_URL
from .auth import build_auth_params
from .types import StrmIdentity


def _require_public_base() -> str:
    """
    Get the configured STRM public base URL.
    
    Returns:
        str: The base URL with any trailing slash removed.
    
    Raises:
        ValueError: If STRM_PUBLIC_BASE_URL is not set or is empty.
    """
    base = (STRM_PUBLIC_BASE_URL or "").strip()
    if not base:
        raise ValueError("STRM_PUBLIC_BASE_URL is required for STRM proxy URLs")
    return base.rstrip("/")


def _encode_params(params: Mapping[str, str]) -> str:
    """
    Encode query parameters into a deterministic URL-encoded query string.
    
    Parameters:
        params (Mapping[str, str]): Mapping of query parameter names to values; keys are sorted in ascending order before encoding.
    
    Returns:
        str: URL-encoded query string with parameters ordered by key.
    """
    return urlencode(sorted(params.items()))


def _build_url(path: str, params: Mapping[str, str]) -> str:
    """
    Build an absolute STRM proxy URL by joining the configured public base with the provided path and appending encoded query parameters if present.
    
    Parameters:
        path (str): Path relative to the STRM public base (leading slash optional).
        params (Mapping[str, str]): Query parameters; keys and values are strings and will be deterministically sorted and URL-encoded.
    
    Returns:
        str: Absolute URL under the configured STRM public base, including a query string when `params` is non-empty.
    """
    from loguru import logger

    logger.trace("Building STRM proxy URL for {}", path)
    base = _require_public_base()
    base_with_slash = base + "/"
    full = urljoin(base_with_slash, path.lstrip("/"))
    if params:
        return f"{full}?{_encode_params(params)}"
    return full


def is_already_proxied(url: str) -> bool:
    """
    Determine whether a URL points to the STRM proxy endpoints.
    
    If the configured STRM_PUBLIC_BASE_URL is empty or unset, this function returns `false`.
    
    Returns:
        `true` if the URL targets the STRM proxy endpoints (i.e. starts with the public base followed by `strm/`), `false` otherwise.
    """
    from loguru import logger

    base = STRM_PUBLIC_BASE_URL.strip()
    if not base:
        return False
    base = base.rstrip("/") + "/"
    is_proxied = url.startswith(base + "strm/")
    logger.trace("URL already proxied? {} -> {}", url, is_proxied)
    return is_proxied


def build_stream_url(identity: StrmIdentity) -> str:
    """
    Constructs a stable STRM proxy stream URL for the given identity.
    
    Parameters:
        identity (StrmIdentity): Identity providing `site`, `slug`, `season`, `episode`, `language`, and optional `provider`; used to populate the stream query parameters.
    
    Returns:
        url (str): Absolute URL to the STRM proxy `/strm/stream` endpoint containing the identity parameters and merged authentication parameters.
    """
    from loguru import logger

    logger.debug("Building STRM stream URL for {}", identity.cache_key())
    params: dict[str, str] = {
        "site": identity.site,
        "slug": identity.slug,
        "s": str(identity.season),
        "e": str(identity.episode),
        "lang": identity.language,
    }
    if identity.provider:
        params["provider"] = identity.provider
    params.update(build_auth_params(params))
    return _build_url("/strm/stream", params)


def build_proxy_url(upstream_url: str) -> str:
    """
    Constructs a STRM proxy URL for an upstream resource.
    
    If `upstream_url` already targets the STRM proxy, it is returned unchanged.
    
    Parameters:
        upstream_url (str): The original resource URL to proxy.
    
    Returns:
        str: The STRM proxy URL. Returns `upstream_url` unchanged when it already points to the STRM proxy; otherwise returns a proxy endpoint URL that includes authentication parameters and the original URL as the `u` query parameter.
    """
    from loguru import logger

    logger.trace("Building STRM proxy URL for {}", upstream_url)
    if is_already_proxied(upstream_url):
        return upstream_url
    parsed = urlsplit(upstream_url)
    name = (parsed.path or "").rsplit("/", 1)[-1].strip()
    if not name or "." not in name:
        name = "resource.bin"
    params = {"u": upstream_url}
    params.update(build_auth_params(params))
    return _build_url(f"/strm/proxy/{name}", params)