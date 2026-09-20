from __future__ import annotations

import ipaddress
import socket
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter

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


def _resolve_public_addresses(host: str, port: int) -> tuple[str, ...]:
    """Resolve a host once and reject empty, private, or mixed DNS answers."""
    normalized = host.strip().rstrip(".").lower()
    if not normalized:
        raise socket.gaierror("empty hostname")
    if normalized in {"localhost", "localhost.localdomain"}:
        raise ValueError("local hostname")
    if normalized.endswith((".local", ".internal", ".home", ".lan")):
        raise ValueError("local hostname")

    try:
        literal = ipaddress.ip_address(normalized)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise ValueError("non-public address")
        return (str(literal),)

    address_infos = socket.getaddrinfo(
        normalized,
        port,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )
    addresses = tuple(
        dict.fromkeys(
            info[4][0]
            for info in address_infos
            if info[4] and isinstance(info[4][0], str)
        )
    )
    if not addresses:
        raise socket.gaierror("hostname resolved without an address")
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("hostname resolved to a non-public address")
    return addresses


def host_is_public(host: str) -> bool:
    """Return whether a host currently resolves only to public addresses."""
    try:
        _resolve_public_addresses(host, 443)
    except OSError, ValueError:
        return False
    return True


class _PinnedHTTPSAdapter(HTTPAdapter):
    """Connect to one validated IP while authenticating the original hostname."""

    def __init__(self, *, address: str, hostname: str, port: int) -> None:
        self._address = address
        self._hostname = hostname
        self._port = port
        super().__init__()

    def get_connection_with_tls_context(
        self,
        request: requests.PreparedRequest,
        verify: bool | str,
        proxies: Mapping[str, str] | None = None,
        cert: Any = None,
    ) -> Any:
        # The pool connects to the approved IP. Certificate verification and
        # SNI still use the provider hostname, so TLS remains end-to-end valid.
        del proxies
        host_params, pool_kwargs = self.build_connection_pool_key_attributes(
            request,
            verify,
            cert,
        )
        del host_params
        pool_kwargs["assert_hostname"] = self._hostname
        pool_kwargs["server_hostname"] = self._hostname
        return self.poolmanager.connection_from_host(
            self._address,
            port=self._port,
            scheme="https",
            pool_kwargs=pool_kwargs,
        )


def _request_pinned_https(
    url: str,
    *,
    address: str,
    hostname: str,
    port: int,
    headers: Mapping[str, str],
    timeout_seconds: float | int,
) -> requests.Response:
    request_headers = dict(headers)
    default_port = port == 443
    try:
        host_literal = ipaddress.ip_address(hostname)
    except ValueError:
        host_literal = None
    host_name = (
        f"[{hostname}]" if host_literal and host_literal.version == 6 else hostname
    )
    host_header = host_name if default_port else f"{host_name}:{port}"
    request_headers["Host"] = host_header

    with requests.Session() as session:
        # A proxy would resolve or connect on our behalf, defeating IP pinning.
        session.trust_env = False
        session.mount(
            "https://",
            _PinnedHTTPSAdapter(address=address, hostname=hostname, port=port),
        )
        return session.get(
            url,
            headers=request_headers,
            timeout=timeout_seconds,
            allow_redirects=False,
            verify=True,
        )


def _validate_request_url(url: str, *, stage: str) -> tuple[str, int, str]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not parsed.netloc or not host:
        raise UnsupportedProviderResponseError(
            f"{stage} returned an invalid HTTPS URL.",
            stage=stage,
            host=host or None,
        )
    if parsed.username or parsed.password:
        raise UnsupportedProviderResponseError(
            f"{stage} returned a URL containing user information.",
            stage=stage,
            host=host,
        )
    try:
        port = parsed.port or 443
        addresses = _resolve_public_addresses(host, port)
    except (OSError, ValueError) as exc:
        raise UnsupportedProviderResponseError(
            f"{stage} could not resolve to a public address.",
            stage=stage,
            host=host,
        ) from exc
    return host, port, addresses[0]


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
) -> requests.Response:
    """Fetch a URL with verified TLS and a bounded, SSRF-safe redirect chain."""
    current_url = url
    expected_origin = allowed_origin.rstrip("/") if allowed_origin else None

    for _redirect_number in range(_MAX_HTTP_REDIRECTS + 1):
        if expected_origin and describe_url(current_url) != expected_origin:
            raise UnsupportedProviderResponseError(
                f"{stage} left the configured catalogue origin.",
                stage=stage,
                host=urlparse(current_url).hostname,
            )
        host, port, address = _validate_request_url(current_url, stage=stage)
        try:
            response = _request_pinned_https(
                current_url,
                address=address,
                hostname=host,
                port=port,
                headers=headers or {},
                timeout_seconds=timeout_seconds,
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
