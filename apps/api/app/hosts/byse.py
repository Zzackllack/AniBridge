from __future__ import annotations

from .base import VideoHost


HOST = VideoHost(
    name="Byse",
    hints=(),
    resolver=lambda _url: None,
    hostname_pattern=r"byse[a-z0-9-]*\.[a-z]{2,}",
    https_only=True,
)
