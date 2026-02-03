from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.cors import apply_cors_middleware


def _make_app(*, origins: list[str], allow_credentials: bool) -> FastAPI:
    app = FastAPI()

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    apply_cors_middleware(app, origins=origins, allow_credentials=allow_credentials)
    return app


def test_cors_wildcard_disables_credentials() -> None:
    app = _make_app(origins=['*'], allow_credentials=True)
    client = TestClient(app)

    res = client.options(
        '/health',
        headers={
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'GET',
        },
    )

    assert res.status_code == 200
    assert res.headers.get('access-control-allow-origin') == '*'
    assert 'access-control-allow-credentials' not in res.headers


def test_cors_specific_origin_allows_credentials_when_enabled() -> None:
    app = _make_app(origins=['http://localhost:5173'], allow_credentials=True)
    client = TestClient(app)

    res = client.options(
        '/health',
        headers={
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'GET',
        },
    )

    assert res.status_code == 200
    assert res.headers.get('access-control-allow-origin') == 'http://localhost:5173'
    assert res.headers.get('access-control-allow-credentials') == 'true'


def test_cors_off_adds_no_headers() -> None:
    app = _make_app(origins=[], allow_credentials=True)
    client = TestClient(app)

    res = client.options(
        '/health',
        headers={
            'Origin': 'http://localhost:5173',
            'Access-Control-Request-Method': 'GET',
        },
    )

    assert res.status_code == 405
    assert 'access-control-allow-origin' not in res.headers
