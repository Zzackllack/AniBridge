"""HEAD fallbacks must describe the representation, not the one-byte probe."""

import asyncio

import httpx
import pytest

from app.catalog import stream_transport


def _client(monkeypatch, responses):
    calls = []
    original = httpx.AsyncClient

    def fetch(request):
        calls.append((request.method, request.headers.get("range")))
        return responses[request.method](request)

    def factory(**kwargs):
        return original(transport=httpx.MockTransport(fetch), **kwargs)

    async def address(host, port):
        return "8.8.8.8"

    monkeypatch.setattr(stream_transport.httpx, "AsyncClient", factory)
    monkeypatch.setattr(stream_transport, "address", address)
    return calls


def test_head_fallback_reports_the_full_length_without_a_range(monkeypatch):
    calls = _client(
        monkeypatch,
        {
            "HEAD": lambda request: httpx.Response(405),
            "GET": lambda request: httpx.Response(
                206,
                headers={
                    "Content-Range": "bytes 0-0/4321",
                    "Content-Length": "1",
                    "Content-Type": "video/mp4",
                },
                content=b"x",
            ),
        },
    )

    async def run():
        opened = await stream_transport.open_stream(
            "https://media.example/movie.mp4", "HEAD", None
        )
        try:
            assert opened.status_code == 200
            assert opened.headers["content-length"] == "4321"
            assert "content-range" not in opened.headers
        finally:
            await opened.close()

    asyncio.run(run())
    assert calls == [("HEAD", None), ("GET", "bytes=0-0")]


def test_head_fallback_does_not_invent_a_length_for_an_unknown_total(monkeypatch):
    _client(
        monkeypatch,
        {
            "HEAD": lambda request: httpx.Response(405),
            "GET": lambda request: httpx.Response(
                206,
                headers={
                    "Content-Range": "bytes 0-0/*",
                    "Content-Length": "1",
                    "Content-Type": "video/mp4",
                },
                content=b"x",
            ),
        },
    )

    async def run():
        opened = await stream_transport.open_stream(
            "https://media.example/movie.mp4", "HEAD", None
        )
        try:
            assert opened.status_code == 200
            assert "content-range" not in opened.headers
            assert "content-length" not in opened.headers
        finally:
            await opened.close()

    asyncio.run(run())


def test_head_fallback_preserves_an_explicit_client_range(monkeypatch):
    calls = _client(
        monkeypatch,
        {
            "HEAD": lambda request: httpx.Response(501),
            "GET": lambda request: httpx.Response(
                206,
                headers={
                    "Content-Range": "bytes 10-19/4321",
                    "Content-Length": "10",
                    "Content-Type": "video/mp4",
                },
                content=b"x" * 10,
            ),
        },
    )

    async def run():
        opened = await stream_transport.open_stream(
            "https://media.example/movie.mp4", "HEAD", "bytes=10-19"
        )
        try:
            assert opened.status_code == 206
            assert opened.headers["content-length"] == "10"
            assert opened.headers["content-range"] == "bytes 10-19/4321"
        finally:
            await opened.close()

    asyncio.run(run())
    assert calls == [("HEAD", "bytes=10-19"), ("GET", "bytes=10-19")]


def test_supported_head_keeps_its_headers_unchanged(monkeypatch):
    calls = _client(
        monkeypatch,
        {
            "HEAD": lambda request: httpx.Response(
                200,
                headers={"Content-Length": "4321", "Content-Type": "video/mp4"},
            )
        },
    )

    async def run():
        opened = await stream_transport.open_stream(
            "https://media.example/movie.mp4", "HEAD", None
        )
        try:
            assert opened.status_code == 200
            assert opened.headers["content-length"] == "4321"
        finally:
            await opened.close()

    asyncio.run(run())
    assert calls == [("HEAD", None)]


@pytest.mark.parametrize("status", [200, 403, 404, 416, 503])
def test_head_fallback_preserves_a_full_response_or_upstream_error(monkeypatch, status):
    _client(
        monkeypatch,
        {
            "HEAD": lambda request: httpx.Response(405),
            "GET": lambda request: httpx.Response(
                status, headers={"Content-Length": "4321", "Content-Type": "video/mp4"}
            ),
        },
    )

    async def run():
        opened = await stream_transport.open_stream(
            "https://media.example/movie.mp4", "HEAD", None
        )
        try:
            assert opened.status_code == status
            assert opened.headers["content-length"] == "4321"
        finally:
            await opened.close()

    asyncio.run(run())


def test_playback_head_does_not_add_zero_length_for_an_unknown_representation(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    from starlette.requests import Request

    from app.catalog import strm_http

    _client(
        monkeypatch,
        {
            "HEAD": lambda request: httpx.Response(405),
            "GET": lambda request: httpx.Response(
                206,
                headers={"Content-Range": "bytes 0-0/*", "Content-Length": "1"},
                content=b"x",
            ),
        },
    )
    playback = strm_http.Playback(
        SimpleNamespace(),
        SimpleNamespace(download_dir=tmp_path),
        {"s.to": "https://example.org"},
        (),
    )
    monkeypatch.setattr(playback, "accepted", lambda job_id: {"provider": "s.to"})

    async def run():
        response = await playback.serve(
            Request({"type": "http", "method": "HEAD", "headers": []}),
            "test-job",
            "https://media.example/movie.mp4",
        )
        assert response.status_code == 200
        assert response.body == b""
        assert "content-length" not in response.headers
        assert "content-range" not in response.headers
        assert not playback.opened

    asyncio.run(run())
