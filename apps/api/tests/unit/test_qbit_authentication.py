"""Real qBittorrent routers behind the same session boundary as production."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from app.api.qbittorrent import router
from app.api.qbittorrent.security import QbitAuth, install

PASSWORD = "private-password-12345"
SECRET = "independent-random-session-secret-123456789"


def application(*, password=PASSWORD, secure=False, query=False):
    app = FastAPI()
    install(app, QbitAuth("operator", password, SECRET, secure))
    if query:
        from app.catalog.qbit_http import router as query_router

        app.include_router(query_router)
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


@pytest.mark.parametrize("query", [False, True])
def test_unauthorized_requests_never_enter_either_mode(query):
    with TestClient(application(query=query)) as client:
        for path in ("app/version", "torrents/info", "sync/maindata", "transfer/info"):
            response = client.get("/api/v2/" + path)
            assert (
                response.status_code == 403
                and response.headers["cache-control"] == "no-store"
            )
        assert (
            client.post("/api/v2/torrents/delete", data={"hashes": "all"}).status_code
            == 403
        )
        assert client.get("/health").status_code == 200
        denied = client.post(
            "/api/v2/auth/login", data={"username": "operator", "password": "wrong"}
        )
        assert (
            denied.status_code == 403 and denied.text == "Fails." and not denied.cookies
        )


def test_login_tamper_expiry_restart_rotation_logout_and_cookie_flags(monkeypatch):
    app = application(secure=True)
    clock = [1800000000]
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: clock[0])
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/v2/auth/login", data={"username": "operator", "password": PASSWORD}
        )
        assert response.status_code == 200 and response.text == "Ok."
        cookie = response.cookies["SID"]
        assert all(
            flag in response.headers["set-cookie"].lower()
            for flag in (
                "httponly",
                "secure",
                "samesite=strict",
                "path=/api/v2",
                "max-age=3600",
            )
        )
        assert client.get("/api/v2/app/version").status_code == 200
        # A fresh application uses the same independently configured secret.
        with TestClient(application(), base_url="https://testserver") as restarted:
            restarted.cookies.set("SID", cookie, path="/api/v2")
            assert restarted.get("/api/v2/app/version").status_code == 200
        with TestClient(application(password=PASSWORD + "rotated")) as rotated:
            rotated.cookies.set("SID", cookie, path="/api/v2")
            assert rotated.get("/api/v2/app/version").status_code == 403
        assert client.post("/api/v2/auth/logout").status_code == 200
        assert client.get("/api/v2/app/version").status_code == 403
        client.cookies.clear()
        client.cookies.set(
            "SID", cookie[:-1] + ("a" if cookie[-1] != "a" else "b"), path="/api/v2"
        )
        assert client.get("/api/v2/app/version").status_code == 403
        client.cookies.set("SID", cookie, path="/api/v2")
        clock[0] += 3601
        assert client.get("/api/v2/app/version").status_code == 403


def test_cross_origin_and_bounded_failed_login_admission():
    with TestClient(application()) as client:
        assert (
            client.post(
                "/api/v2/auth/login",
                data={"username": "operator", "password": PASSWORD},
                headers={"Origin": "https://untrusted.invalid"},
            ).status_code
            == 403
        )
        for _ in range(60):
            assert (
                client.post(
                    "/api/v2/auth/login",
                    data={"username": "private-user", "password": "private-password"},
                ).status_code
                == 403
            )
        response = client.post(
            "/api/v2/auth/login", data={"username": "operator", "password": PASSWORD}
        )
        assert (
            response.status_code == 429
            and 1 <= int(response.headers["retry-after"]) <= 61
        )


@pytest.mark.parametrize(
    "values",
    [
        ("operator", "", ""),
        ("", PASSWORD, SECRET),
        ("operator", "short", SECRET),
        ("operator", PASSWORD, "short"),
    ],
)
def test_partial_or_weak_configuration_is_refused(values):
    with pytest.raises(ValueError, match="together"):
        QbitAuth(*values)
