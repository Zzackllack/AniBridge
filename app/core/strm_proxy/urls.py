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
    base = STRM_PUBLIC_BASE_URL.strip()
    if not base:
        return False
    base = base.rstrip("/") + "/"
    return url.startswith(base + "strm/")


def build_stream_url(identity: StrmIdentity) -> str:
    """
    Build a stable STRM stream URL for the given identity.
    """
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
    if is_already_proxied(upstream_url):
        return upstream_url
    params = {"u": upstream_url}
    params.update(build_auth_params(params))
    return _build_url("/strm/proxy", params)
