from __future__ import annotations

from typing import Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger

from app.utils.logger import config as configure_logger

configure_logger()

_SESSION: Optional[requests.Session] = None


def _build_session() -> requests.Session:
    s = requests.Session()

    # Conservative retry policy for transient network hiccups
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.verify = True
    logger.info(f"HTTP client TLS verify: {'on' if s.verify else 'off'}")
    return s


def get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = _build_session()
    return _SESSION


def get(url: str, *, timeout: float | int = 20, **kwargs: Any) -> requests.Response:
    s = get_session()
    try:
        return s.get(url, timeout=timeout, **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if "bytes missing" in msg or "incomplete" in msg:
            headers = dict(kwargs.get("headers") or {})
            headers["Accept-Encoding"] = "identity"
            logger.warning(
                "HTTP GET retry with Accept-Encoding=identity due to decode error"
            )
            # remove old headers to avoid duplication
            kwargs = {k: v for k, v in kwargs.items() if k != "headers"}
            return s.get(url, timeout=timeout, headers=headers, **kwargs)
        raise


def post(url: str, *, timeout: float | int = 30, **kwargs: Any) -> requests.Response:
    s = get_session()
    try:
        return s.post(url, timeout=timeout, **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if "bytes missing" in msg or "incomplete" in msg:
            headers = dict(kwargs.get("headers") or {})
            headers["Accept-Encoding"] = "identity"
            logger.warning(
                "HTTP POST retry with Accept-Encoding=identity due to decode error"
            )
            kwargs = {k: v for k, v in kwargs.items() if k != "headers"}
            return s.post(url, timeout=timeout, headers=headers, **kwargs)
        raise
