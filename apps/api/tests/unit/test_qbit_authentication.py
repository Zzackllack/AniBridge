"""Real qBittorrent routers behind the same session boundary as production."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from app.api.qbittorrent import router
from app.api.qbittorrent.security import QbitAuth, install

PASSWORD = "private-password-12345"
SECRET = "independent-random-session-secret-123456789"


def application(
    *, username="operator", password=PASSWORD, secret=SECRET, secure=False, query=False
):
    app = FastAPI()
    install(app, QbitAuth(username, password, secret, secure))
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


@pytest.mark.parametrize(
    "changed", [{"username": "new-operator"}, {"secret": SECRET + "rotated"}]
)
def test_username_and_secret_rotation_reject_existing_session(changed):
    with TestClient(application()) as client:
        login = client.post(
            "/api/v2/auth/login", data={"username": "operator", "password": PASSWORD}
        )
        assert login.status_code == 200
        cookie = login.cookies["SID"]
    with TestClient(application(**changed)) as rotated:
        rotated.cookies.set("SID", cookie, path="/api/v2")
        assert rotated.get("/api/v2/app/version").status_code == 403


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


def test_mounted_application_cannot_bypass_auth_and_scopes_its_cookie():
    parent = FastAPI()
    parent.mount("/bridge", application())
    with TestClient(parent) as client:
        assert client.get("/bridge/api/v2/app/version").status_code == 403
        response = client.post(
            "/bridge/api/v2/auth/login",
            data={"username": "operator", "password": PASSWORD},
        )
        assert response.status_code == 200 and response.text == "Ok."
        assert "path=/bridge/api/v2" in response.headers["set-cookie"].lower()
        assert client.get("/bridge/api/v2/app/version").status_code == 200
        assert client.post("/bridge/api/v2/auth/logout").status_code == 200
        assert client.get("/bridge/api/v2/app/version").status_code == 403


def test_secure_ingress_origin_with_an_internal_http_proxy_hop():
    app = application(secure=True)

    async def proxy(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "scheme": "http"}
        await app(scope, receive, send)

    with TestClient(proxy, base_url="https://private.example") as client:
        response = client.post(
            "/api/v2/auth/login",
            data={"username": "operator", "password": PASSWORD},
            headers={"Origin": "https://private.example"},
        )
        assert (
            response.status_code == 200
            and "secure" in response.headers["set-cookie"].lower()
        )
        assert client.get("/api/v2/app/version").status_code == 200
        for origin in (
            "null",
            "https://other.example",
            "http://private.example",
            "https://private.example:444",
            "https://private.example:0",
            "https://private.example/path",
        ):
            assert (
                client.post(
                    "/api/v2/auth/logout", headers={"Origin": origin}
                ).status_code
                == 403
            )
        assert (
            client.post(
                "/api/v2/auth/logout", headers={"Origin": "https://private.example:443"}
            ).status_code
            == 200
        )


def test_production_wiring_uses_secure_cookies_by_default(request, monkeypatch):
    for key, value in {
        "QBIT_USERNAME": "operator",
        "QBIT_PASSWORD": PASSWORD,
        "QBIT_SESSION_SECRET": SECRET,
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("QBIT_COOKIE_SECURE", raising=False)
    client = request.getfixturevalue("client")
    client.base_url = "https://testserver"
    assert client.get("/api/v2/app/version").status_code == 403
    response = client.post(
        "/api/v2/auth/login", data={"username": "operator", "password": PASSWORD}
    )
    assert (
        response.status_code == 200
        and "secure" in response.headers["set-cookie"].lower()
    )
    assert client.get("/api/v2/app/version").status_code == 200
