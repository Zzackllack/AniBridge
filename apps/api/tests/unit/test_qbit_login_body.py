"""Reject oversized login input before FastAPI allocates or parses a form."""

import asyncio

import httpx
import pytest
from test_qbit_authentication import PASSWORD, application


@pytest.mark.parametrize("chunked", [False, True])
def test_login_bounds_declared_and_chunked_bodies_before_credential_processing(chunked):
    app = application()
    processed = []
    app.state.qbit_auth.credentials_match = lambda *args: processed.append(args) or True
    payload = (
        "username=operator&password=" + PASSWORD + "&padding=" + "x" * 32768
    ).encode()

    async def run():
        async def stream():
            yield payload[:100]
            yield payload[100:]
            raise AssertionError("oversized input must not be drained")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/v2/auth/login",
                content=stream() if chunked else payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert response.status_code == 413 and not response.cookies
            assert response.headers["cache-control"] == "no-store"
            assert not processed
            assert (await client.get("/health")).status_code == 200

    asyncio.run(run())


def test_fragmented_urlencoded_and_multipart_logins_keep_normal_form_behavior():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application()),
            base_url="http://testserver",
        ) as client:

            async def fragmented():
                for value in (b"username=", b"operator&password=", PASSWORD.encode()):
                    yield value

            response = await client.post(
                "/api/v2/auth/login",
                content=fragmented(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert response.status_code == 200 and response.cookies.get("SID")
            response = await client.post(
                "/api/v2/auth/login",
                files={"username": (None, "operator"), "password": (None, PASSWORD)},
            )
            assert response.status_code == 200 and response.cookies.get("SID")

    asyncio.run(run())


def test_slow_body_times_out_without_blocking_other_requests(monkeypatch):
    from app.api.qbittorrent import login_body

    monkeypatch.setattr(login_body, "LOGIN_DEADLINE_S", 0.01)

    async def run():
        async def slow():
            yield b"username=operator"
            await asyncio.Event().wait()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application()),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v2/auth/login",
                content=slow(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert response.status_code == 408 and not response.cookies
            assert (await client.get("/health")).status_code == 200

    asyncio.run(run())


def test_empty_asgi_frames_are_bounded_before_stream_filtering():
    from app.api.qbittorrent.login_body import LOGIN_FRAMES, bounded_receive

    calls = 0

    async def receive():
        nonlocal calls
        calls += 1
        return {"type": "http.request", "body": b"", "more_body": True}

    response = asyncio.run(bounded_receive({"type": "http", "headers": []}, receive))
    assert response.status_code == 413 and calls == LOGIN_FRAMES
