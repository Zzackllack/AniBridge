from __future__ import annotations

from app.core.downloader.extractors.voe import resolve_direct_link_from_redirect

from .base import VideoHost


HOST = VideoHost(
    name="VOE",
    hints=("voe",),
    resolver=lambda url: resolve_direct_link_from_redirect(
        redirect_url=url,
        site="",
    ),
)
