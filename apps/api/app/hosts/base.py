from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Optional
from urllib.parse import urlsplit


HostResolver = Callable[[str], Optional[str]]


@dataclass(frozen=True, slots=True)
class VideoHost:
    """Describe one supported video host and how to extract its direct URL."""

    name: str
    hints: tuple[str, ...]
    resolver: HostResolver
    hostname_pattern: str | None = None
    https_only: bool = False

    def matches(self, url: str) -> bool:
        """Return whether this host can handle the given embed URL."""
        parsed = urlsplit(url)
        host = parsed.hostname
        if not host:
            return False
        host = host.lower()
        if self.https_only and parsed.scheme != "https":
            return False
        if self.hostname_pattern is not None:
            return re.fullmatch(self.hostname_pattern, host) is not None
        return any(hint in host for hint in self.hints)

    def resolve(self, url: str) -> Optional[str]:
        """Resolve a host embed URL into a direct media URL."""
        return self.resolver(url)
