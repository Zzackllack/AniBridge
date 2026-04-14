from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlsplit


HostResolver = Callable[[str], Optional[str]]


@dataclass(frozen=True, slots=True)
class VideoHost:
    """Describe one supported video host and how to extract its direct URL."""

    name: str
    hints: tuple[str, ...]
    resolver: HostResolver

    def matches(self, url: str) -> bool:
        """Return whether this host can handle the given embed URL."""
        host = urlsplit(url).hostname
        if not host:
            return False
        host = host.lower()
        return any(hint in host for hint in self.hints)

    def resolve(self, url: str) -> Optional[str]:
        """Resolve a host embed URL into a direct media URL."""
        return self.resolver(url)
