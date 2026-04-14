from __future__ import annotations

from .base import VideoHost
from .bridge import resolve_via_aniworld


HOST = VideoHost(
    name="LoadX",
    hints=("loadx",),
    resolver=lambda url: resolve_via_aniworld(
        module_name="loadx",
        function_name="get_direct_link_from_loadx",
        url=url,
        host_name="LoadX",
    ),
)
