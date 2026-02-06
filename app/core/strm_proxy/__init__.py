from .types import StrmIdentity
from .urls import build_proxy_url, build_stream_url, is_already_proxied
from .hls import (
    build_synthetic_master_playlist,
    inject_stream_inf_bandwidth_hints,
    is_hls_media_playlist,
    rewrite_hls_playlist,
)
from .cache import MEMORY_CACHE, StrmCacheEntry
from .remux import REMUX_CACHE_MANAGER, RemuxDecision
from .auth import build_auth_params, require_auth


def resolve_direct_url(identity: StrmIdentity):
    """
    Resolve a direct provider URL for a STRM identity using a lazy import.
    """
    from .resolver import resolve_direct_url as _resolve_direct_url

    return _resolve_direct_url(identity)


__all__ = [
    "StrmIdentity",
    "resolve_direct_url",
    "build_proxy_url",
    "build_stream_url",
    "is_already_proxied",
    "rewrite_hls_playlist",
    "inject_stream_inf_bandwidth_hints",
    "is_hls_media_playlist",
    "build_synthetic_master_playlist",
    "MEMORY_CACHE",
    "StrmCacheEntry",
    "REMUX_CACHE_MANAGER",
    "RemuxDecision",
    "build_auth_params",
    "require_auth",
]
