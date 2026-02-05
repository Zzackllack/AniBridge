from __future__ import annotations

from typing import Mapping
from urllib.parse import urlencode, urljoin, urlsplit

from app.config import STRM_PUBLIC_BASE_URL
from .auth import build_auth_params
from .types import StrmIdentity


def _require_public_base() -> str:
    """
    Return the configured public base URL or raise when missing.
    """
    base = (STRM_PUBLIC_BASE_URL or "").strip()
    if not base:
        raise ValueError("STRM_PUBLIC_BASE_URL is required for STRM proxy URLs")
    return base.rstrip("/")


def _encode_params(params: Mapping[str, str]) -> str:
    """
    Encode query parameters in a deterministic order.
    """
    return urlencode(sorted(params.items()))


def _build_url(path: str, params: Mapping[str, str]) -> str:
    """
    Build an absolute URL under the public base with the given path and params.
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
    Return True when a URL already targets the STRM proxy endpoints.
    """
    from loguru import logger

    base = (STRM_PUBLIC_BASE_URL or "").strip()
    if not base:
        return False
    base = base.rstrip("/") + "/"
    is_proxied = url.startswith(base + "strm/")
    logger.trace("URL already proxied? {} -> {}", url, is_proxied)
    return is_proxied


def build_stream_url(identity: StrmIdentity) -> str:
    """
    Build a stable STRM stream URL for the given identity.
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
    Build a proxy URL for an arbitrary upstream resource.
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
