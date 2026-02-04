import httpx
from fastapi import FastAPI, Request, Response


def _build_upstream_app():
    app = FastAPI()

    @app.get("/ok")
    async def ok():
        return Response(content=b"ok", media_type="video/mp4")

    @app.get("/fail")
    async def fail():
        return Response(content=b"forbidden", status_code=403, media_type="text/plain")

    @app.get("/range")
    async def range_handler(request: Request):
        payload = b"0123456789"
        rng = request.headers.get("range")
        if rng == "bytes=0-4":
            return Response(
                content=payload[:5],
                status_code=206,
                headers={
                    "Content-Range": "bytes 0-4/10",
                    "Accept-Ranges": "bytes",
                    "Content-Length": "5",
                },
                media_type="video/mp4",
            )
        return Response(
            content=payload,
            headers={"Accept-Ranges": "bytes", "Content-Length": "10"},
            media_type="video/mp4",
        )

    return app


def _patch_async_client(monkeypatch, upstream_app):
    def _factory():
        transport = httpx.ASGITransport(app=upstream_app)
        return httpx.AsyncClient(
            transport=transport,
            base_url="http://upstream",
            follow_redirects=True,
            trust_env=False,
        )

    monkeypatch.setattr("app.api.strm._build_async_client", _factory)


def test_strm_stream_refreshes_on_failure(client, monkeypatch):
    upstream_app = _build_upstream_app()
    _patch_async_client(monkeypatch, upstream_app)

    calls = {"n": 0}

    def _resolve(identity):
        calls["n"] += 1
        if calls["n"] == 1:
            return "http://upstream/fail", "VOE"
        return "http://upstream/ok", "VOE"

    monkeypatch.setattr("app.api.strm.resolve_direct_url", _resolve)

    resp = client.get(
        "/strm/stream",
        params={
            "site": "aniworld.to",
            "slug": "show",
            "s": "1",
            "e": "1",
            "lang": "German Dub",
        },
    )
    assert resp.status_code == 200
    assert resp.content == b"ok"
    assert calls["n"] == 2


def test_strm_proxy_forwards_range(client, monkeypatch):
    upstream_app = _build_upstream_app()
    _patch_async_client(monkeypatch, upstream_app)

    resp = client.get(
        "/strm/proxy",
        params={"u": "http://upstream/range"},
        headers={"Range": "bytes=0-4"},
    )
    assert resp.status_code == 206
    assert resp.content == b"01234"
    assert resp.headers.get("Content-Range") == "bytes 0-4/10"
