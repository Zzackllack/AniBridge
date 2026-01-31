from urllib.parse import parse_qs, urlparse

import requests

import app.utils.title_resolver as tr


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _payload_for(term: str) -> dict:
    if term == "911":
        return {
            "shows": [
                {"name": "Reno 911!", "url": "/serie/reno-911"},
                {"name": "Road to 9/11", "url": "/serie/road-to-911"},
            ]
        }
    if term == "9-1-1":
        return {
            "shows": [
                {"name": "9-1-1", "url": "/serie/9-1-1"},
                {"name": "9-1-1: Lone Star", "url": "/serie/9-1-1-lone-star"},
            ]
        }
    return {"shows": []}


def _fake_http_get(url: str, timeout: int = 15):
    term = parse_qs(urlparse(url).query).get("term", [""])[0]
    return _FakeResponse(_payload_for(term))


def test_build_sto_search_terms() -> None:
    assert tr._build_sto_search_terms("911") == ["911", "9-1-1"]
    assert tr._build_sto_search_terms("9-1-1") == ["9-1-1", "911"]


def test_search_sto_slug_prefers_best_match(monkeypatch) -> None:
    monkeypatch.setattr(tr, "http_get", _fake_http_get)
    assert tr._search_sto_slug("911") == "9-1-1"


def test_search_sto_slug_handles_network_error(monkeypatch) -> None:
    def _fake_error_first(url: str, timeout: int = 15):
        term = parse_qs(urlparse(url).query).get("term", [""])[0]
        if term == "911":
            raise requests.exceptions.RequestException("boom")
        return _FakeResponse(_payload_for(term))

    monkeypatch.setattr(tr, "http_get", _fake_error_first)
    assert tr._search_sto_slug("911") == "9-1-1"


def test_search_sto_slug_handles_malformed_payload(monkeypatch) -> None:
    def _fake_malformed_first(url: str, timeout: int = 15):
        term = parse_qs(urlparse(url).query).get("term", [""])[0]
        if term == "911":
            return _FakeResponse({"shows": "nope"})
        return _FakeResponse(_payload_for(term))

    monkeypatch.setattr(tr, "http_get", _fake_malformed_first)
    assert tr._search_sto_slug("911") == "9-1-1"
