from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="Vidmoly",
    hints=("vidmoly",),
    resolver=lambda url: resolve_via_aniworld(
        module_name="vidmoly",
        function_name="get_direct_link_from_vidmoly",
        url=url,
        host_name="Vidmoly",
    ),
)
