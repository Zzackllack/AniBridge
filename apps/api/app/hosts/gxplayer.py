from __future__ import annotations

import re
from typing import Optional

from loguru import logger

from app.utils.domain_resolver import get_megakino_base_url
from app.utils.http_client import get as http_get

from .base import VideoHost


def resolve_gxplayer(url: str) -> Optional[str]:
    """Resolve a gxplayer embed page to the exposed master playlist URL."""
    logger.debug("GXPlayer direct link probe: {}", url)
    try:
        response = http_get(
            url,
            timeout=20,
            headers={"Referer": get_megakino_base_url().rstrip("/")},
        )
    except Exception as exc:
        logger.warning("GXPlayer host fetch failed: {}", exc)
        return None

    uid_match = re.search(r'"uid":"(.*?)"', response.text)
    md5_match = re.search(r'"md5":"(.*?)"', response.text)
    id_match = re.search(r'"id":"(.*?)"', response.text)
    if not all([uid_match, md5_match, id_match]):
        return None

    uid = uid_match.group(1)
    md5 = md5_match.group(1)
    video_id = id_match.group(1)
    return (
        f"https://watch.gxplayer.xyz/m3u8/{uid}/{md5}/master.txt"
        f"?s=1&id={video_id}&cache=1"
    )


HOST = VideoHost(
    name="GXPlayer",
    hints=("gxplayer",),
    resolver=resolve_gxplayer,
)
