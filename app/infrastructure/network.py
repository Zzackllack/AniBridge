from __future__ import annotations

import os
from typing import Dict, Optional
from loguru import logger
from app.utils.logger import config as configure_logger

from app.config import (
    PROXY_ENABLED,
    PROXY_APPLY_ENV,
    PROXY_DISABLE_CERT_VERIFY,
    EFFECTIVE_HTTP_PROXY,
    EFFECTIVE_HTTPS_PROXY,
    EFFECTIVE_ALL_PROXY,
    EFFECTIVE_NO_PROXY,
    PROXY_FORCE_REMOTE_DNS,
    PROXY_IP_CHECK_INTERVAL_MIN,
    PROXY_SCOPE,
    PUBLIC_IP_CHECK_ENABLED,
    PUBLIC_IP_CHECK_INTERVAL_MIN,
)
import requests
from contextlib import contextmanager

configure_logger()


def _mask(url: str | None) -> str:
    """Mask credentials in a proxy URL for safe logging."""
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


def proxies_mapping() -> Dict[str, str]:
    """Return a requests-compatible proxies mapping if proxying is enabled.

    Keys: 'http', 'https'. Empty dict when disabled or no URL provided.

    Important: Tokens generated for CDN links are IP-bound (contain parameters
    like 'i=' and 'asn='). To avoid 403 from the CDN, the HTTP client used for
    link extraction must egress via the same IP as the downloader. Therefore,
    when PROXY_SCOPE is 'ytdlp', we still route requests via the same proxy
    used by yt-dlp so both phases share the same public IP.
    """
    if not PROXY_ENABLED:
        return {}

    proxies: Dict[str, str] = {}
    if PROXY_SCOPE == "ytdlp":
        # Align requests with yt-dlp proxy to keep IP consistent for tokenized URLs
        p = EFFECTIVE_HTTPS_PROXY or EFFECTIVE_HTTP_PROXY or EFFECTIVE_ALL_PROXY
        if p:
            proxies = {"http": p, "https": p}
            logger.info(
                f"Proxy scope=ytdlp: aligning HTTP client with yt-dlp proxy http=https={_mask(p)}"
            )
        else:
            logger.debug("Proxy scope=ytdlp but no effective proxy URL configured.")
            return {}
    else:
        # Determine protocol-specific proxies (falling back to ALL/PROXY_URL handled in config)
        http = EFFECTIVE_HTTP_PROXY or EFFECTIVE_ALL_PROXY
        https = EFFECTIVE_HTTPS_PROXY or EFFECTIVE_ALL_PROXY or http
        if http:
            proxies["http"] = http
        if https:
            proxies["https"] = https

    if proxies:
        logger.info(
            f"Requests proxies active: http={_mask(proxies.get('http'))} https={_mask(proxies.get('https'))}"
        )
    else:
        logger.debug("Requests proxies inactive or not configured.")
    return proxies


def apply_global_proxy_env() -> None:
    """Apply proxy configuration to process environment for broad compatibility.

    Sets uppercase and lowercase variants so that urllib/requests/yt-dlp and
    many third-party libraries will honor proxy settings automatically.
    """
    if not PROXY_ENABLED:
        logger.info("Proxy disabled: outbound traffic uses direct connection.")
        return
    # Even for PROXY_SCOPE=ytdlp we export env so tools honoring env vars
    # (including some provider libraries) share the same egress IP as yt-dlp.
    if not PROXY_APPLY_ENV:
        logger.info("Proxy enabled but PROXY_APPLY_ENV=false (env vars not exported).")
        return

    http = EFFECTIVE_HTTP_PROXY or EFFECTIVE_ALL_PROXY
    https = EFFECTIVE_HTTPS_PROXY or EFFECTIVE_ALL_PROXY or http
    no_proxy = EFFECTIVE_NO_PROXY

    env_updates = {}
    if http:
        env_updates.update({"HTTP_PROXY": http, "http_proxy": http})
    if https:
        env_updates.update({"HTTPS_PROXY": https, "https_proxy": https})
    # Also set ALL_PROXY for libraries that honor it
    any_proxy = https or http
    if any_proxy:
        env_updates.update({"ALL_PROXY": any_proxy, "all_proxy": any_proxy})
    if no_proxy:
        env_updates.update({"NO_PROXY": no_proxy, "no_proxy": no_proxy})

    for k, v in env_updates.items():
        os.environ[k] = v
    if env_updates:
        logger.info(
            f"Proxy env applied: HTTP_PROXY={_mask(os.getenv('HTTP_PROXY'))} "
            f"HTTPS_PROXY={_mask(os.getenv('HTTPS_PROXY'))} NO_PROXY={os.getenv('NO_PROXY') or ''}"
        )


def yt_dlp_proxy() -> Optional[str]:
    """Return a proxy URL suitable for passing to yt-dlp's 'proxy' option.

    Prefers HTTPS proxy, falls back to HTTP/ALL. Returns None when disabled.
    """
    if not PROXY_ENABLED:
        return None
    if PROXY_SCOPE == "requests":
        logger.info("Proxy scope=requests: yt-dlp will not use proxy.")
        return None
    proxy = EFFECTIVE_HTTPS_PROXY or EFFECTIVE_HTTP_PROXY or EFFECTIVE_ALL_PROXY
    if proxy:
        logger.info(f"yt-dlp proxy in use: {_mask(proxy)}")
    else:
        logger.debug("yt-dlp proxy not set despite PROXY_ENABLED=true.")
    return proxy


def requests_verify() -> bool:
    """Return TLS verification flag for requests sessions."""
    return not PROXY_DISABLE_CERT_VERIFY


def log_proxy_config_summary() -> None:
    """Emit a one-line summary of proxy configuration at startup."""
    if not PROXY_ENABLED:
        logger.info("Proxy: disabled")
        return
    http = EFFECTIVE_HTTP_PROXY or EFFECTIVE_ALL_PROXY
    https = EFFECTIVE_HTTPS_PROXY or EFFECTIVE_ALL_PROXY or http
    remote_dns = PROXY_FORCE_REMOTE_DNS or (
        (http or "").startswith("socks5h://") or (https or "").startswith("socks5h://")
    )
    logger.info(
        f"Proxy: enabled http={_mask(http)} https={_mask(https)} "
        f"dns={'remote' if remote_dns else 'local'} verify_tls={'on' if requests_verify() else 'off'}"
    )
    logger.warning(
        "Proxy integration is experimental and may be unreliable. Prefer a full VPN (e.g., Gluetun) for production."
    )


def _fetch_public_ip() -> Optional[str]:
    endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
    ]
    s = requests.Session()
    # Make the IP check reflect the active proxy scope.
    # - scope=all/requests: use requests proxies
    # - scope=ytdlp: route via yt-dlp proxy so it shows download egress IP
    prox: Dict[str, str] = {}
    if PROXY_SCOPE == "ytdlp":
        p = yt_dlp_proxy()
        if p:
            prox = {"http": p, "https": p}
    else:
        prox = proxies_mapping()
    if prox:
        s.proxies.update(prox)
    # Avoid decode issues on flaky proxies
    s.headers.update({"Accept-Encoding": "identity"})
    s.verify = requests_verify()
    for url in endpoints:
        try:
            r = s.get(url, timeout=5)
            if r.status_code == 200:
                ip = (r.text or "").strip()
                if ip:
                    return ip
        except Exception as e:
            logger.debug(f"Public IP fetch failed via {url}: {e}")
    return None


def start_ip_check_thread(
    stop_event: "threading.Event",
) -> Optional["threading.Thread"]:
    """Start a background thread that periodically logs the current public IP.

    Runs when either proxy is enabled or PUBLIC_IP_CHECK_ENABLED=true. Interval
    is taken from PUBLIC_IP_CHECK_INTERVAL_MIN when the latter is enabled,
    otherwise falls back to PROXY_IP_CHECK_INTERVAL_MIN.
    """
    import threading

    if not (PROXY_ENABLED or PUBLIC_IP_CHECK_ENABLED):
        return None

    interval = (
        max(0, int(PUBLIC_IP_CHECK_INTERVAL_MIN))
        if PUBLIC_IP_CHECK_ENABLED
        else max(0, int(PROXY_IP_CHECK_INTERVAL_MIN))
    )
    if interval == 0:
        logger.debug("Proxy IP check disabled (interval=0).")
        return None

    def _loop():
        logger.info(f"Starting public IP monitor: interval={interval} min")
        # Do an immediate check
        ip = _fetch_public_ip()
        if ip:
            logger.info(f"Public IP: {ip}")
        else:
            logger.warning("Public IP: unavailable")
        while not stop_event.wait(interval * 60):
            ip = _fetch_public_ip()
            if ip:
                logger.info(f"Public IP: {ip}")
            else:
                logger.warning("Public IP: unavailable")

    t = threading.Thread(target=_loop, name="proxy-ip", daemon=True)
    t.start()
    return t


@contextmanager
def disabled_proxy_env():
    """Temporarily disable proxy environment variables within the context.

    This affects libraries that read proxies from env (e.g., requests in
    aniworld.*). Intended for last-resort fallback when proxyed resolution
    is blocked and a direct connection is acceptable.
    """
    keys = [
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ]
    saved: Dict[str, Optional[str]] = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            if k in os.environ:
                del os.environ[k]
        logger.info("Temporarily disabled proxy env for fallback resolution.")
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]
        logger.info("Restored proxy env after fallback resolution.")
