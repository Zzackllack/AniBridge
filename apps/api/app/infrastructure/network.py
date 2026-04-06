from __future__ import annotations

import threading
from typing import Optional

import requests
from loguru import logger

from app.config import PUBLIC_IP_CHECK_ENABLED, PUBLIC_IP_CHECK_INTERVAL_MIN
from app.utils.logger import config as configure_logger

configure_logger()


# Kept for safe logging in system reports where URLs may embed credentials.
def _mask(url: str | None) -> str:
    """Mask credentials in a URL for safe logging."""
    if not url:
        return ""
    try:
        from urllib.parse import urlsplit, urlunsplit

        p = urlsplit(url)
        netloc = p.netloc
        if "@" in netloc:
            userinfo, host = netloc.split("@", 1)
            if ":" in userinfo:
                user, _ = userinfo.split(":", 1)
            else:
                user = userinfo
            netloc = f"{user}:****@{host}"
        p2 = (p.scheme, netloc, p.path or "", p.query or "", p.fragment or "")
        return urlunsplit(p2)
    except Exception:
        return url


def _fetch_public_ip() -> Optional[str]:
    endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
    ]
    s = requests.Session()
    for url in endpoints:
        try:
            r = s.get(url, timeout=5)
            if r.status_code == 200:
                ip = (r.text or "").strip()
                if ip:
                    return ip
        except Exception as e:
            logger.debug("Public IP fetch failed via {}: {}", url, e)
    return None


def start_ip_check_thread(
    stop_event: threading.Event,
) -> Optional[threading.Thread]:
    """Start a background thread that periodically logs the current public IP."""
    if not PUBLIC_IP_CHECK_ENABLED:
        return None

    interval = max(0, int(PUBLIC_IP_CHECK_INTERVAL_MIN))
    if interval == 0:
        logger.debug("Public IP check disabled (interval=0).")
        return None

    def _loop() -> None:
        logger.info("Starting public IP monitor: interval={} min", interval)
        ip = _fetch_public_ip()
        if ip:
            logger.info("Public IP: {}", ip)
        else:
            logger.warning("Public IP: unavailable")
        while not stop_event.wait(interval * 60):
            ip = _fetch_public_ip()
            if ip:
                logger.info("Public IP: {}", ip)
            else:
                logger.warning("Public IP: unavailable")

    t = threading.Thread(target=_loop, name="public-ip", daemon=True)
    t.start()
    return t
