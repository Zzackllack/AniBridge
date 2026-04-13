from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="VOE",
    hints=("voe",),
    resolver=lambda url: resolve_via_aniworld(
        module_name="voe",
        function_name="get_direct_link_from_voe",
        url=url,
        host_name="VOE",
    ),
)
