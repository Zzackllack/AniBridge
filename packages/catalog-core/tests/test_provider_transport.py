"""No live network: pinned pool, admission, response classification and bounds."""

import asyncio
import socket
from email.utils import formatdate

import httpx
import pytest
from test_megakino_session import Stream

from catalog_core.providers.transport import (
    AdmissionDeferred,
    Session,
    _global_address,
    fetch,
    retry_after,
)


def test_retry_after_seconds_dates_and_bounds():
    assert retry_after("12", 100) == 12
    assert retry_after(formatdate(150, usegmt=True), 100) == 50
    assert retry_after(formatdate(90, usegmt=True), 100) == 1
    assert retry_after("0") == 1
    assert retry_after("9999999") == 86400
    assert retry_after("nonsense") == 60


def test_movie_pagination_is_bounded_on_an_explicit_mirror_origin(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, stream=Stream(b"metadata"))

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(respond)
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )

    async def scenario():
        origin = "https://mirror.example"
        response = await fetch(origin, "/movies", query={"page": "175"})
        assert response.outcome == "ok"
        assert calls[0].headers["host"] == "mirror.example"
        assert calls[0].url.query == b"page=175"
        for query in (
            {"page": "0"},
            {"page": "10001"},
            {"page": "2", "url": "https://other.example"},
        ):
            with pytest.raises(ValueError):
                await fetch(origin, "/movies", query=query)
        assert len(calls) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "origin,path,query,allowed",
    [
        (
            "https://api.radarr.video",
            "/v1/search",
            {"q": "Example Film", "year": "2020"},
            True,
        ),
        (
            "https://provider.example",
            "/v1/search",
            {"q": "Example", "year": "2020"},
            False,
        ),
        (
            "https://api.radarr.video",
            "/v1/movie/123",
            {"q": "Example", "year": "2020"},
            False,
        ),
        (
            "https://api.radarr.video",
            "/v1/search",
            {"q": "Example", "year": "2020", "url": "https://other.example"},
            False,
        ),
        ("https://api.radarr.video", "/v1/search", {"q": "", "year": "2020"}, False),
        (
            "https://api.radarr.video",
            "/v1/search",
            {"q": "x" * 513, "year": "2020"},
            False,
        ),
        (
            "https://api.radarr.video",
            "/v1/search",
            {"q": "Example", "year": "0"},
            False,
        ),
        (
            "https://api.radarr.video",
            "/v1/search",
            {"q": "Example", "year": "2020.0"},
            False,
        ),
    ],
)
def test_radarr_title_queries_stay_on_the_bounded_metadata_route(
    monkeypatch, origin, path, query, allowed
):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, stream=Stream(b"[]"))

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(respond)
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )

    async def scenario():
        if allowed:
            result = await fetch(origin, path, query=query)
            assert result.outcome == "ok"
        else:
            with pytest.raises(ValueError):
                await fetch(origin, path, query=query)

    asyncio.run(scenario())
    assert len(calls) == int(allowed)
    if allowed:
        assert calls[0].headers["Host"] == "api.radarr.video"
        assert dict(calls[0].url.params) == query


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
                if status in (429, 503):
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


@pytest.mark.parametrize(
    "answer",
    [
        "64:ff9b::7f00:1",
        "64:ff9b::a00:1",
        "224.0.0.1",
        "ff02::1",
        "0.0.0.0",
        "192.0.0.1",
        "2001:db8::1",
        "100.64.0.1",
    ],
)
def test_dns_rejects_transition_multicast_and_reserved_answers(monkeypatch, answer):
    calls = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET6, 1, 6, "", (answer, 443, 0, 0))],
    )
    monkeypatch.setattr(
        httpx,
        "AsyncHTTPTransport",
        lambda **kwargs: httpx.MockTransport(lambda request: calls.append(request)),
    )
    result = asyncio.run(fetch("https://provider.example", "/episode"))
    assert result.outcome == "unexpected_structure" and calls == []


@pytest.mark.parametrize(
    "answer,allowed",
    [
        ("8.8.8.8", True),
        ("::ffff:8.8.8.8", True),
        ("64:ff9b::808:808", True),
        ("64:ff9b::7f00:1", False),
        ("2002:7f00:1::", False),
        ("127.0.0.1", False),
    ],
)
def test_global_address_unwraps_embedded_ipv4(answer, allowed):
    assert _global_address(answer) is allowed


@pytest.mark.parametrize(
    "origin,path,query,allowed",
    [
        (
            "https://skyhook.sonarr.tv",
            "/v2/tvdb/search",
            {"term": "Example", "language": "eng"},
            True,
        ),
        (
            "https://skyhook.sonarr.tv",
            "/v2/tvdb/search",
            {"term": "Example", "language": "eng", "url": "https://other.example"},
            False,
        ),
        (
            "https://skyhook.sonarr.tv",
            "/v1/tvdb/search/en/",
            {"term": "Example"},
            True,
        ),
        (
            "https://skyhook.sonarr.tv",
            "/v1/tvdb/search/en/",
            {"term": "Example", "language": "eng"},
            False,
        ),
        (
            "https://api.themoviedb.org",
            "/3/search/movie",
            {"query": "Example", "year": "2020"},
            True,
        ),
        (
            "https://api.themoviedb.org",
            "/3/search/movie",
            {"query": "Example", "year": "20"},
            False,
        ),
        (
            "https://api.themoviedb.org",
            "/3/find/tt1234567",
            {"external_source": "imdb_id"},
            True,
        ),
        (
            "https://api.themoviedb.org",
            "/3/find/tt1234567",
            {"external_source": "other"},
            False,
        ),
        (
            "https://api.themoviedb.org",
            "/3/search/movie",
            {"query": "Example", "year": "2020", "api_key": "secret"},
            False,
        ),
    ],
)
def test_canonical_query_shapes_are_enumerated(
    monkeypatch, origin, path, query, allowed
):
    calls = []
    monkeypatch.setattr(
        httpx,
        "AsyncHTTPTransport",
        lambda **kwargs: httpx.MockTransport(
            lambda request: (
                calls.append(request) or httpx.Response(200, stream=Stream(b"[]"))
            )
        ),
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )

    async def scenario():
        if allowed:
            result = await fetch(origin, path, query=query)
            assert result.outcome == "ok"
        else:
            with pytest.raises(ValueError):
                await fetch(origin, path, query=query)

    asyncio.run(scenario())
    assert len(calls) == int(allowed)


def test_pool_timeout_is_a_local_resource_outcome(monkeypatch):
    def timeout(request):
        raise httpx.PoolTimeout("sensitive URL must not be emitted")

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(timeout)
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    result = asyncio.run(fetch("https://provider.example", "/episode"))
    assert result.outcome == "local_resource" and result.error_class == "PoolTimeout"


def test_canonical_pool_retains_identifying_default_headers(monkeypatch):
    def respond(request):
        assert request.headers["User-Agent"] == "AniBridge-Metadata/1.0"
        assert request.headers["Accept"] == "*/*"
        assert request.headers["Accept-Encoding"] == "identity"
        assert (
            "cookie" not in request.headers and "authorization" not in request.headers
        )
        return httpx.Response(200, stream=Stream(b"[]"))

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(respond)
    )
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )

    async def scenario():
        session = Session("https://skyhook.sonarr.tv", 1)
        try:
            result = await session.fetch(
                session.origin, "/v1/tvdb/search/en/", query={"term": "example"}
            )
            assert result.outcome == "ok" and result.body == b"[]"
        finally:
            await session.close()

    asyncio.run(scenario())
