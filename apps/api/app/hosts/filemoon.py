from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="Filemoon",
    hints=("filemoon",),
    resolver=lambda url: resolve_via_aniworld(
        module_name="filemoon",
        function_name="get_direct_link_from_filemoon",
        url=url,
        host_name="Filemoon",
    ),
)
