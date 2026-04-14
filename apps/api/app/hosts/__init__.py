from __future__ import annotations

from .base import VideoHost
from .doodstream import HOST as DOODSTREAM
from .filemoon import HOST as FILEMOON
from .gxplayer import HOST as GXPLAYER
from .loadx import HOST as LOADX
from .luluvdo import HOST as LULUVDO
from .streamtape import HOST as STREAMTAPE
from .vidoza import HOST as VIDOZA
from .vidmoly import HOST as VIDMOLY
from .voe import HOST as VOE

VIDEO_HOSTS: tuple[VideoHost, ...] = (
    VOE,
    DOODSTREAM,
    FILEMOON,
    STREAMTAPE,
    VIDMOLY,
    LOADX,
    LULUVDO,
    VIDOZA,
    GXPLAYER,
)

VIDEO_HOSTS_BY_NAME = {host.name: host for host in VIDEO_HOSTS}


def get_host(name: str) -> VideoHost | None:
    """Return one configured video host by its canonical name."""
    return VIDEO_HOSTS_BY_NAME.get(name)


def detect_host(url: str) -> VideoHost | None:
    """Return the first configured video host matching the given URL."""
    for host in VIDEO_HOSTS:
        if host.matches(url):
            return host
    return None


def resolve_host_url(url: str) -> tuple[str | None, str]:
    """Resolve a host embed URL and return its canonical host name."""
    host = detect_host(url)
    if host is None:
        return None, "EMBED"
    return host.resolve(url), host.name


def is_supported_host_url(url: str) -> bool:
    """Return whether any configured video host recognizes the URL."""
    return detect_host(url) is not None


__all__ = [
    "VIDEO_HOSTS",
    "VIDEO_HOSTS_BY_NAME",
    "VideoHost",
    "detect_host",
    "get_host",
    "is_supported_host_url",
    "resolve_host_url",
]
