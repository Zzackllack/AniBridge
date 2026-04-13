from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="Luluvdo",
    hints=("luluvdo",),
    resolver=lambda url: resolve_via_aniworld(
        module_name="luluvdo",
        function_name="get_direct_link_from_luluvdo",
        url=url,
        host_name="Luluvdo",
    ),
)
