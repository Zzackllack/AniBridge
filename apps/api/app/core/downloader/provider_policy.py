from __future__ import annotations

import ipaddress
import socket
from functools import lru_cache
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlparse

import requests

from .errors import (
    ProviderTransportError,
    ProviderVerificationRequiredError,
    SourceUnavailableError,
    UnsupportedProviderResponseError,
)

_MAX_HTTP_REDIRECTS = 8


def describe_url(url: str) -> str:
    """Return a log-safe origin without paths, query strings, or tokens."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "<invalid-url>"


def looks_like_verification_page(html: str) -> bool:
    """Recognize challenge documents while avoiding script-only false positives."""
    lowered = (html or "").lower()
    marker_pairs = (
        ("cf-turnstile", "captcha-form"),
        ("cf-turnstile", "verify you are human"),
        ("stream wird vorbereitet", "captcha"),
        ("challenge-platform", "cf-turnstile-response"),
    )
    return any(first in lowered and second in lowered for first, second in marker_pairs)


@lru_cache(maxsize=256)
def host_is_public(host: str) -> bool:
    """Return whether a redirect host is suitable for an outbound request."""
    normalized = host.strip().rstrip(".").lower()
    if not normalized:
        return False
    if normalized in {"localhost", "localhost.localdomain"}:
        return False
    if normalized.endswith((".local", ".internal", ".home", ".lan")):
        return False

    try:
        literal = ipaddress.ip_address(normalized)
    except ValueError:
        literal = None
    if literal is not None:
        return literal.is_global

    try:
        address_infos = socket.getaddrinfo(normalized, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        # A public-looking provider hostname may rotate before local DNS catches up.
        return True

    addresses = {
        info[4][0] for info in address_infos if info[4] and isinstance(info[4][0], str)
    }
    return not addresses or all(
        ipaddress.ip_address(address).is_global for address in addresses
    )


def _validate_request_url(url: str, *, stage: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UnsupportedProviderResponseError(
            f"{stage} returned an invalid HTTP URL.",
            stage=stage,
            host=host or None,
        )
    if not host_is_public(host):
        raise UnsupportedProviderResponseError(
            f"{stage} attempted to redirect to a non-public address.",
            stage=stage,
            host=host,
        )


def _raise_for_response(response: requests.Response, *, stage: str) -> None:
    status_code = int(response.status_code)
    host = urlparse(str(response.url)).hostname
    body = response.text or ""
    if looks_like_verification_page(body):
        raise ProviderVerificationRequiredError(
            f"{stage} requires interactive verification; browser solving is not enabled.",
            stage=stage,
            status_code=status_code,
            host=host,
        )
    if status_code in {404, 410}:
        raise SourceUnavailableError(
            f"{stage} reports that the source is unavailable (HTTP {status_code}).",
            stage=stage,
            status_code=status_code,
            host=host,
        )
    if status_code >= 400:
        raise ProviderTransportError(
            f"{stage} failed with HTTP {status_code}.",
            stage=stage,
            status_code=status_code,
            host=host,
        )


def fetch_verified_response(
    url: str,
    *,
    stage: str,
    timeout_seconds: float | int,
    headers: Mapping[str, str] | None = None,
    allowed_origin: str | None = None,
    requester: Callable[..., Any] | None = None,
) -> requests.Response:
    """Fetch a URL with verified TLS and a bounded, SSRF-safe redirect chain."""
    current_url = url
    expected_origin = allowed_origin.rstrip("/") if allowed_origin else None
    request = requester or requests.get

    for _redirect_number in range(_MAX_HTTP_REDIRECTS + 1):
        _validate_request_url(current_url, stage=stage)
        if expected_origin and describe_url(current_url) != expected_origin:
            raise UnsupportedProviderResponseError(
                f"{stage} left the configured catalogue origin.",
                stage=stage,
                host=urlparse(current_url).hostname,
            )
        try:
            response = request(
                current_url,
                headers=dict(headers or {}),
                timeout=timeout_seconds,
                allow_redirects=False,
                verify=True,
            )
        except requests.RequestException as exc:
            raise ProviderTransportError(
                f"{stage} request failed: {type(exc).__name__}.",
                stage=stage,
                host=urlparse(current_url).hostname,
            ) from exc

        response.url = str(getattr(response, "url", current_url) or current_url)
        is_redirect = bool(getattr(response, "is_redirect", False))
        is_permanent_redirect = bool(getattr(response, "is_permanent_redirect", False))
        if is_redirect or is_permanent_redirect:
            location = getattr(response, "headers", {}).get("Location")
            if not location:
                raise UnsupportedProviderResponseError(
                    f"{stage} returned a redirect without a destination.",
                    stage=stage,
                    status_code=int(response.status_code),
                    host=urlparse(current_url).hostname,
                )
            current_url = urljoin(current_url, location)
            continue

        _raise_for_response(response, stage=stage)
        return response

    raise ProviderTransportError(
        f"{stage} exceeded the {_MAX_HTTP_REDIRECTS}-redirect limit.",
        stage=stage,
        host=urlparse(current_url).hostname,
    )
