"""No live URLs/cookies: generated logical-origin and bounded bootstrap cases."""

import asyncio
import socket

import httpx
import pytest
from catalog_core.providers.megakino_session import bootstrap, fetch
from catalog_core.providers.transport import fetch as ordinary_fetch

TRANSPORT = httpx.AsyncHTTPTransport

ORIGIN = "https://movie.example"
PATH = "/films/1-example.html"
STUB = (
    '<!doctype html><meta charset="utf-8"><script>'
    'fetch("/index.php?yg=token",{credentials:"include"})'
    '.then(function(){ location.replace("' + PATH + '") })'
    ".catch(function(){ location.reload() });</script>"
).encode()


class Stream(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        yield self.body


def fixture(
    monkeypatch,
    *,
    cookie="session=generated; Path=/; Secure; HttpOnly",
    retry=b"<html>real metadata</html>",
    token_status=204,
    token_headers=None,
):
    calls = []
    starts = []

    def response(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, stream=Stream(STUB))
        if len(calls) == 2:
            return httpx.Response(
                token_status,
                headers=token_headers or {"Set-Cookie": cookie},
                stream=Stream(b""),
            )
        return httpx.Response(200, stream=Stream(retry))

    monkeypatch.setattr(
        httpx,
        "AsyncHTTPTransport",
        lambda **kwargs: httpx.MockTransport(response),
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    async def start():
        starts.append(True)

    return calls, starts, start


def test_bootstrap_counts_three_verified_requests_and_logical_secure_cookie(
    monkeypatch,
):
    calls, starts, before = fixture(monkeypatch)
    result = asyncio.run(fetch(ORIGIN, PATH, before_request=before))
    assert result.outcome == "ok" and len(starts) == 3
    assert [r.url.raw_path for r in calls] == [
        PATH.encode(),
        b"/index.php?yg=token",
        PATH.encode(),
    ]
    assert all(
        r.url.host == "93.184.216.34"
        and r.headers["host"] == "movie.example"
        and r.extensions["sni_hostname"] == "movie.example"
        for r in calls
    )
    assert "cookie" not in calls[0].headers and "cookie" not in calls[1].headers
    assert calls[2].headers["cookie"] == "session=generated"


@pytest.mark.parametrize(
    "cookie",
    [
        "session=generated; Domain=example; Path=/",
        "session=generated; Domain=93.184.216.34; Path=/",
        "session=generated; Path=/other; Secure",
    ],
)
def test_wrong_domain_or_path_cookie_never_reaches_retry(monkeypatch, cookie):
    calls, _, _ = fixture(monkeypatch, cookie=cookie)
    assert asyncio.run(fetch(ORIGIN, PATH)).outcome == "ok"
    assert "cookie" not in calls[2].headers


def test_repeat_stub_stops_after_one_retry(monkeypatch):
    calls, _, _ = fixture(monkeypatch, retry=STUB)
    assert asyncio.run(fetch(ORIGIN, PATH)).outcome == "challenge_or_block"
    assert len(calls) == 3


@pytest.mark.parametrize("status", [403, 429, 500])
def test_token_failures_do_not_retry_original(monkeypatch, status):
    calls, _, _ = fixture(monkeypatch, token_status=status)
    assert asyncio.run(fetch(ORIGIN, PATH)).outcome != "ok"
    assert len(calls) == 2


def test_token_redirect_cannot_escape_origin_or_endpoint(monkeypatch):
    calls, _, _ = fixture(
        monkeypatch, token_status=302, token_headers={"Location": "/other?yg=token"}
    )
    assert asyncio.run(fetch(ORIGIN, PATH)).outcome == "unexpected_structure"
    assert len(calls) == 2


def test_ordinary_fetch_cannot_request_token_query(monkeypatch):
    calls, _, _ = fixture(monkeypatch)
    with pytest.raises(ValueError, match="query only"):
        asyncio.run(ordinary_fetch(ORIGIN, "/index.php", query={"yg": "token"}))
    assert not calls


def test_unknown_script_never_triggers_bootstrap():
    assert bootstrap(STUB, PATH)
    assert not bootstrap(STUB, "/other")
    assert not bootstrap(STUB.replace(b"fetch(", b"eval("), PATH)
    assert not bootstrap(b"<html>" + STUB + b"</html>", PATH)


def test_cumulative_body_cap_and_cookie_header_cap(monkeypatch):
    calls, _, _ = fixture(monkeypatch, retry=b"x" * 100)
    assert (
        asyncio.run(fetch(ORIGIN, PATH, body_bytes=len(STUB) + 50)).outcome
        == "unexpected_structure"
    )
    assert len(calls) == 3
    calls, _, _ = fixture(monkeypatch, cookie="session=" + "x" * 8192)
    assert asyncio.run(fetch(ORIGIN, PATH)).outcome == "unexpected_structure"
    assert len(calls) == 2
