from __future__ import annotations

from dataclasses import dataclass, field
import socket

import pytest
import requests

from app.core.downloader.errors import (
    ProviderTransportError,
    ProviderVerificationRequiredError,
    SourceUnavailableError,
    UnsupportedProviderResponseError,
)
from app.core.downloader import provider_policy


@pytest.fixture(autouse=True)
def _resolve_example_hosts_to_public_address(monkeypatch):
    monkeypatch.setattr(
        provider_policy,
        "_resolve_public_addresses",
        lambda _host, _port: ("93.184.216.34",),
    )


@dataclass
class FakeResponse:
    status_code: int
    url: str
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def is_redirect(self) -> bool:
        return self.status_code in {301, 302, 303, 307, 308}

    @property
    def is_permanent_redirect(self) -> bool:
        return self.status_code in {301, 308}


def test_fetch_verified_response_follows_bounded_public_redirects(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []

    def _get(url: str, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            return FakeResponse(
                302,
                url,
                headers={"Location": "https://voe.example/e/token"},
            )
        return FakeResponse(200, url, text="provider page")

    monkeypatch.setattr(provider_policy, "_request_pinned_https", _get)
    response = provider_policy.fetch_verified_response(
        "https://catalog.example/r?token=secret",
        stage="provider redirect",
        timeout_seconds=4,
    )

    assert response.url == "https://voe.example/e/token"
    assert [call[0] for call in calls] == [
        "https://catalog.example/r?token=secret",
        "https://voe.example/e/token",
    ]
    assert all(call[1]["address"] == "93.184.216.34" for call in calls)
    assert [call[1]["hostname"] for call in calls] == [
        "catalog.example",
        "voe.example",
    ]


def test_fetch_verified_response_keeps_configured_origin(monkeypatch):
    calls: list[str] = []

    def _get(url: str, **_kwargs):
        calls.append(url)
        return FakeResponse(
            302,
            url,
            headers={"Location": "https://serienstream.example/episode"},
        )

    monkeypatch.setattr(provider_policy, "_request_pinned_https", _get)
    with pytest.raises(UnsupportedProviderResponseError, match="configured"):
        provider_policy.fetch_verified_response(
            "https://configured.example/episode",
            stage="Serienstream episode metadata",
            timeout_seconds=4,
            allowed_origin="https://configured.example",
        )

    assert calls == ["https://configured.example/episode"]


def test_fetch_verified_response_rejects_private_redirect(monkeypatch):
    def _get(url: str, **_kwargs):
        return FakeResponse(
            302,
            url,
            headers={"Location": "https://127.0.0.1/private"},
        )

    monkeypatch.setattr(
        provider_policy,
        "_resolve_public_addresses",
        lambda host, _port: _reject_private_address(host),
    )
    monkeypatch.setattr(provider_policy, "_request_pinned_https", _get)
    with pytest.raises(UnsupportedProviderResponseError, match="public address"):
        provider_policy.fetch_verified_response(
            "https://catalog.example/r",
            stage="provider redirect",
            timeout_seconds=4,
        )


@pytest.mark.parametrize("status_code", [200, 403, 429, 503])
def test_fetch_verified_response_classifies_challenge(status_code, monkeypatch):
    challenge = "<form id='captcha-form'><div class='cf-turnstile'></div></form>"
    monkeypatch.setattr(
        provider_policy,
        "_request_pinned_https",
        lambda url, **_kwargs: FakeResponse(status_code, url, text=challenge),
    )

    with pytest.raises(ProviderVerificationRequiredError):
        provider_policy.fetch_verified_response(
            "https://catalog.example/r",
            stage="provider redirect",
            timeout_seconds=4,
        )


@pytest.mark.parametrize("status_code", [403, 429, 503])
def test_fetch_verified_response_keeps_unknown_http_error_distinct(
    status_code, monkeypatch
):
    monkeypatch.setattr(
        provider_policy,
        "_request_pinned_https",
        lambda url, **_kwargs: FakeResponse(status_code, url, text="ordinary error"),
    )
    with pytest.raises(ProviderTransportError) as exc_info:
        provider_policy.fetch_verified_response(
            "https://catalog.example/r",
            stage="provider redirect",
            timeout_seconds=4,
        )
    assert exc_info.value.status_code == status_code


@pytest.mark.parametrize("status_code", [404, 410])
def test_fetch_verified_response_classifies_terminal_source(status_code, monkeypatch):
    monkeypatch.setattr(
        provider_policy,
        "_request_pinned_https",
        lambda url, **_kwargs: FakeResponse(status_code, url),
    )
    with pytest.raises(SourceUnavailableError):
        provider_policy.fetch_verified_response(
            "https://voe.example/e/dead",
            stage="VOE page",
            timeout_seconds=4,
        )


def test_challenge_script_on_valid_page_is_not_a_false_positive(monkeypatch):
    html = "<script src='https://challenges.cloudflare.com/turnstile.js'></script><video></video>"
    monkeypatch.setattr(
        provider_policy,
        "_request_pinned_https",
        lambda url, **_kwargs: FakeResponse(200, url, text=html),
    )
    response = provider_policy.fetch_verified_response(
        "https://catalog.example/episode",
        stage="episode metadata",
        timeout_seconds=4,
    )
    assert response.text == html


def test_fetch_verified_response_classifies_timeout(monkeypatch):
    def _timeout(_url: str, **_kwargs):
        raise requests.Timeout("secret-token")

    monkeypatch.setattr(provider_policy, "_request_pinned_https", _timeout)
    with pytest.raises(ProviderTransportError, match="Timeout") as exc_info:
        provider_policy.fetch_verified_response(
            "https://catalog.example/r?token=secret",
            stage="provider redirect",
            timeout_seconds=1,
        )
    assert "secret" not in str(exc_info.value)


def test_describe_url_redacts_paths_and_query_tokens():
    assert (
        provider_policy.describe_url("https://example.test/r?token=secret")
        == "https://example.test"
    )


def test_fetch_verified_response_rejects_plaintext_http_before_request(monkeypatch):
    monkeypatch.setattr(
        provider_policy,
        "_request_pinned_https",
        lambda *_args, **_kwargs: pytest.fail("request was sent"),
    )
    with pytest.raises(UnsupportedProviderResponseError, match="HTTPS"):
        provider_policy.fetch_verified_response(
            "http://catalog.example/r",
            stage="provider redirect",
            timeout_seconds=1,
        )


def test_host_is_public_rejects_dns_failure(monkeypatch):
    def _fail_resolution(_host: str, _port: int) -> tuple[str, ...]:
        raise socket.gaierror("not found")

    monkeypatch.setattr(
        provider_policy,
        "_resolve_public_addresses",
        _fail_resolution,
    )

    assert provider_policy.host_is_public("missing.example") is False


def test_pinned_request_preserves_hostname_for_host_header_and_tls(monkeypatch):
    captured: dict[str, object] = {}

    class FakeSession:
        trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def mount(self, prefix: str, adapter: object) -> None:
            captured["prefix"] = prefix
            captured["adapter"] = adapter

        def get(self, url: str, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return FakeResponse(200, url)

    monkeypatch.setattr(provider_policy.requests, "Session", FakeSession)

    response = provider_policy._request_pinned_https(
        "https://provider.example:8443/watch",
        address="93.184.216.34",
        hostname="provider.example",
        port=8443,
        headers={"User-Agent": "test"},
        timeout_seconds=2,
    )

    adapter = captured["adapter"]
    assert isinstance(adapter, provider_policy._PinnedHTTPSAdapter)
    assert adapter._address == "93.184.216.34"
    assert adapter._hostname == "provider.example"
    assert captured["prefix"] == "https://"
    assert captured["url"] == "https://provider.example:8443/watch"
    assert captured["kwargs"]["headers"]["Host"] == "provider.example:8443"
    assert response.status_code == 200

    pool_call: dict[str, object] = {}

    class FakePoolManager:
        def connection_from_host(self, host: str, **kwargs):
            pool_call["host"] = host
            pool_call.update(kwargs)
            return object()

    adapter.poolmanager = FakePoolManager()
    prepared = requests.Request(
        "GET",
        "https://provider.example:8443/watch",
    ).prepare()
    adapter.get_connection_with_tls_context(prepared, verify=True)

    assert pool_call["host"] == "93.184.216.34"
    assert pool_call["port"] == 8443
    assert pool_call["pool_kwargs"]["assert_hostname"] == "provider.example"
    assert pool_call["pool_kwargs"]["server_hostname"] == "provider.example"


def _reject_private_address(host: str) -> tuple[str, ...]:
    if host == "127.0.0.1":
        raise ValueError("private")
    return ("93.184.216.34",)
