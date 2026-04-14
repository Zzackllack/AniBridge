from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="Vidoza",
    hints=("vidoza",),
    resolver=lambda url: resolve_via_aniworld(
        module_name="vidoza",
        function_name="get_direct_link_from_vidoza",
        url=url,
        host_name="Vidoza",
    ),
)
