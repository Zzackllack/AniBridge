"""Query handlers must remain the first match for overlapping qBittorrent paths."""

from types import SimpleNamespace

import pytest

from app.api.route_order import QUERY_QBITTORRENT_OVERLAP, assert_query_precedence


def _route(module: str, path: str, *methods: str):
    return SimpleNamespace(
        path=path,
        methods=set(methods),
        endpoint=SimpleNamespace(__module__=module),
    )


def test_query_router_before_legacy_router_is_accepted():
    routes = [
        _route("app.catalog.qbit_http", path, method)
        for method, path in QUERY_QBITTORRENT_OVERLAP
    ]
    routes.extend(
        _route("app.api.qbittorrent.torrents", path, method)
        for method, path in QUERY_QBITTORRENT_OVERLAP
    )
    assert_query_precedence(routes)


def test_legacy_router_shadowing_a_query_route_fails_startup():
    path = "/api/v2/torrents/info"
    with pytest.raises(RuntimeError, match="GET /api/v2/torrents/info"):
        assert_query_precedence(
            [
                _route("app.api.qbittorrent.torrents", path, "GET"),
                _route("app.catalog.qbit_http", path, "GET"),
            ]
        )


def test_non_overlapping_routes_do_not_participate():
    assert_query_precedence(
        [
            _route("app.api.qbittorrent.app_meta", "/api/v2/app/version", "GET"),
            _route("app.catalog.qbit_http", "/api/v2/torrents/add", "POST"),
        ]
    )
