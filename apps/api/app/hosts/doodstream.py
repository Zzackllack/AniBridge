from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="Doodstream",
    hints=("dood", "d0000d"),
    resolver=lambda url: resolve_via_aniworld(
        module_name="doodstream",
        function_name="get_direct_link_from_doodstream",
        url=url,
        host_name="Doodstream",
    ),
)
