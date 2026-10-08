"""No live network: pinned pool, admission, response classification and bounds."""

import asyncio
import socket
from email.utils import formatdate

import httpx
import pytest
from catalog_core.providers.transport import (
    AdmissionDeferred,
    Session,
    fetch,
    retry_after,
)
from test_megakino_session import Stream


def test_retry_after_seconds_dates_and_bounds():
    assert retry_after("12", 100) == 12
    assert retry_after(formatdate(150, usegmt=True), 100) == 50
    assert retry_after(formatdate(90, usegmt=True), 100) == 1
    assert retry_after("0") == 1
    assert retry_after("9999999") == 86400
    assert retry_after("nonsense") == 60


@pytest.mark.parametrize(
    "status,outcome",
    [
        (200, "ok"),
        (401, "challenge_or_block"),
        (403, "challenge_or_block"),
        (429, "rate_limited"),
        (503, "transport_failure"),
        (400, "http_error"),
    ],
)
def test_status_and_pool_scope(monkeypatch, status, outcome):
    calls, pools = [], []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            status,
            headers={"Retry-After": "12", "Set-Cookie": "private=secret"},
            stream=Stream(b"body"),
        )

    def transport(**kwargs):
        pools.append(kwargs)
        return httpx.MockTransport(respond)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", transport)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )

    async def scenario():
        session = Session("https://provider.example", headers={"User-Agent": "fixed"})
        try:
            for _ in range(2):
                r = await session.fetch("https://provider.example", "/episode")
                assert r.outcome == outcome and r.status == status and r.requests == 1
                if status == 429:
                    assert r.retry_after == 12
            with pytest.raises(ValueError, match="origin mismatch"):
                await session.fetch("https://other.example", "/episode")
        finally:
            await session.close()

    asyncio.run(scenario())
    assert (
        len(pools) == 1
        and pools[0]["trust_env"] is False
        and pools[0]["verify"] is True
    )
    assert all(
        r.url.host == "93.184.216.34"
        and r.headers["Host"] == "provider.example"
        and r.extensions["sni_hostname"] == "provider.example"
        and r.headers["Accept-Encoding"] == "identity"
        and "cookie" not in r.headers
        for r in calls
    )


def test_admission_is_outside_network_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr(
        httpx,
        "AsyncHTTPTransport",
        lambda **kwargs: httpx.MockTransport(lambda r: calls.append(r)),
    )

    async def before():
        await asyncio.sleep(0.02)
        raise AdmissionDeferred(3600)

    with pytest.raises(AdmissionDeferred):
        asyncio.run(
            fetch(
                "https://provider.example",
                "/episode",
                deadline=0.001,
                before_request=before,
            )
        )
    assert calls == []


def test_dns_every_hop_rejects_unsafe_answer(monkeypatch):
    calls = []
    answers = iter(["93.184.216.34", "127.0.0.1"])
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (next(answers), 443))]
    )

    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "/second"}, stream=Stream(b""))

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **k: httpx.MockTransport(respond)
    )
    r = asyncio.run(fetch("https://provider.example", "/first"))
    assert r.outcome == "unexpected_structure" and len(calls) == 1
