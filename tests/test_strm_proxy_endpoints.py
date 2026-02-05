import httpx
from fastapi import FastAPI, Request, Response


def _build_upstream_app():
    """
    Create an in-memory FastAPI app that simulates upstream endpoints used by tests.
    
    The returned app exposes:
    - GET /ok: responds 200 with body b"ok" and media_type "video/mp4".
    - GET /fail: responds 403 with body b"forbidden" and media_type "text/plain".
    - GET /range: responds to Range header "bytes=0-4" with 206 Partial Content,
      content b"01234", and headers "Content-Range", "Accept-Ranges", and "Content-Length";
      otherwise responds with the full payload b"0123456789" and appropriate headers.
    
    Returns:
        FastAPI: A configured FastAPI application instance representing the upstream service.
    """
    app = FastAPI()

    @app.get("/ok")
    async def ok():
        """
        Return an HTTP 200 response with body "ok" and media type "video/mp4".
        
        Returns:
            starlette.responses.Response: A response whose content is `b"ok"`, media_type is `"video/mp4"`, and status code is 200.
        """
        return Response(content=b"ok", media_type="video/mp4")

    @app.get("/fail")
    async def fail():
        """
        Return an HTTP 403 Forbidden response with a plain-text body.
        
        Returns:
            fastapi.Response: Response with status code 403, content b"forbidden", and media_type "text/plain".
        """
        return Response(content=b"forbidden", status_code=403, media_type="text/plain")

    @app.get("/range")
    async def range_handler(request: Request):
        """
        Handle a GET request that serves a 10-byte payload and supports a single byte range.
        
        If the request's Range header equals "bytes=0-4", returns a 206 Partial Content response with bytes 0–4 and headers `Content-Range: "bytes 0-4/10"`, `Accept-Ranges: "bytes"`, and `Content-Length: "5"`. Otherwise returns the full 10-byte payload with `Accept-Ranges: "bytes"` and `Content-Length: "10"`.
        
        Returns:
            Response: A FastAPI Response containing the requested bytes and appropriate status and headers.
        """
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
    """
    Patch the module factory used to build AsyncClient instances so it creates an httpx.AsyncClient backed by the provided ASGI app.
    
    Parameters:
        monkeypatch: pytest monkeypatch fixture used to set module attributes.
        upstream_app: ASGI/FastAPI application to mount into the client's transport.
    """
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
        """
        Return a simulated upstream resolution that yields a failing URL on the first invocation and a succeeding URL on subsequent invocations.
        
        Parameters:
            identity (str): Ignored input; the function always returns "VOE" as the resolved identity.
        
        Returns:
            tuple: (url, identity) where `url` is "http://upstream/fail" on the first call and "http://upstream/ok" thereafter, and `identity` is "VOE".
        """
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