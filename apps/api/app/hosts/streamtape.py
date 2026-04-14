from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="Streamtape",
    hints=("streamtape", "streamta.pe"),
    resolver=lambda url: resolve_via_aniworld(
        module_name="streamtape",
        function_name="get_direct_link_from_streamtape",
        url=url,
        host_name="Streamtape",
    ),
)
