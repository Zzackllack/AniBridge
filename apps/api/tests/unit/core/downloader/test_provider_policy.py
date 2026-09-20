from __future__ import annotations

from dataclasses import dataclass, field

import pytest
import requests

from app.core.downloader.errors import (
    ProviderTransportError,
    ProviderVerificationRequiredError,
    SourceUnavailableError,
    UnsupportedProviderResponseError,
)
from app.core.downloader import provider_policy


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

    monkeypatch.setattr(provider_policy, "host_is_public", lambda _host: True)
    response = provider_policy.fetch_verified_response(
        "https://catalog.example/r?token=secret",
        stage="provider redirect",
        timeout_seconds=4,
        requester=_get,
    )

    assert response.url == "https://voe.example/e/token"
    assert [call[0] for call in calls] == [
        "https://catalog.example/r?token=secret",
        "https://voe.example/e/token",
    ]
    assert all(call[1]["verify"] is True for call in calls)
    assert all(call[1]["allow_redirects"] is False for call in calls)


def test_fetch_verified_response_keeps_configured_origin(monkeypatch):
    calls: list[str] = []

    def _get(url: str, **_kwargs):
        calls.append(url)
        return FakeResponse(
            302,
            url,
            headers={"Location": "https://serienstream.example/episode"},
        )

    monkeypatch.setattr(provider_policy, "host_is_public", lambda _host: True)
    with pytest.raises(UnsupportedProviderResponseError, match="configured"):
        provider_policy.fetch_verified_response(
            "https://configured.example/episode",
            stage="Serienstream episode metadata",
            timeout_seconds=4,
            allowed_origin="https://configured.example",
            requester=_get,
        )

    assert calls == ["https://configured.example/episode"]


def test_fetch_verified_response_rejects_private_redirect(monkeypatch):
    def _get(url: str, **_kwargs):
        return FakeResponse(
            302,
            url,
            headers={"Location": "http://127.0.0.1/private"},
        )

    monkeypatch.setattr(
        provider_policy,
        "host_is_public",
        lambda host: host != "127.0.0.1",
    )
    with pytest.raises(UnsupportedProviderResponseError, match="non-public"):
        provider_policy.fetch_verified_response(
            "https://catalog.example/r",
            stage="provider redirect",
            timeout_seconds=4,
            requester=_get,
        )


@pytest.mark.parametrize("status_code", [200, 403, 429, 503])
def test_fetch_verified_response_classifies_challenge(status_code, monkeypatch):
    challenge = "<form id='captcha-form'><div class='cf-turnstile'></div></form>"
    monkeypatch.setattr(provider_policy, "host_is_public", lambda _host: True)

    with pytest.raises(ProviderVerificationRequiredError):
        provider_policy.fetch_verified_response(
            "https://catalog.example/r",
            stage="provider redirect",
            timeout_seconds=4,
            requester=lambda url, **_kwargs: FakeResponse(
                status_code, url, text=challenge
            ),
        )


@pytest.mark.parametrize("status_code", [403, 429, 503])
def test_fetch_verified_response_keeps_unknown_http_error_distinct(
    status_code, monkeypatch
):
    monkeypatch.setattr(provider_policy, "host_is_public", lambda _host: True)
    with pytest.raises(ProviderTransportError) as exc_info:
        provider_policy.fetch_verified_response(
            "https://catalog.example/r",
            stage="provider redirect",
            timeout_seconds=4,
            requester=lambda url, **_kwargs: FakeResponse(
                status_code, url, text="ordinary error"
            ),
        )
    assert exc_info.value.status_code == status_code


@pytest.mark.parametrize("status_code", [404, 410])
def test_fetch_verified_response_classifies_terminal_source(status_code, monkeypatch):
    monkeypatch.setattr(provider_policy, "host_is_public", lambda _host: True)
    with pytest.raises(SourceUnavailableError):
        provider_policy.fetch_verified_response(
            "https://voe.example/e/dead",
            stage="VOE page",
            timeout_seconds=4,
            requester=lambda url, **_kwargs: FakeResponse(status_code, url),
        )


def test_challenge_script_on_valid_page_is_not_a_false_positive(monkeypatch):
    html = "<script src='https://challenges.cloudflare.com/turnstile.js'></script><video></video>"
    monkeypatch.setattr(provider_policy, "host_is_public", lambda _host: True)
    response = provider_policy.fetch_verified_response(
        "https://catalog.example/episode",
        stage="episode metadata",
        timeout_seconds=4,
        requester=lambda url, **_kwargs: FakeResponse(200, url, text=html),
    )
    assert response.text == html


def test_fetch_verified_response_classifies_timeout(monkeypatch):
    monkeypatch.setattr(provider_policy, "host_is_public", lambda _host: True)

    def _timeout(_url: str, **_kwargs):
        raise requests.Timeout("secret-token")

    with pytest.raises(ProviderTransportError, match="Timeout") as exc_info:
        provider_policy.fetch_verified_response(
            "https://catalog.example/r?token=secret",
            stage="provider redirect",
            timeout_seconds=1,
            requester=_timeout,
        )
    assert "secret" not in str(exc_info.value)


def test_describe_url_redacts_paths_and_query_tokens():
    assert (
        provider_policy.describe_url("https://example.test/r?token=secret")
        == "https://example.test"
    )
