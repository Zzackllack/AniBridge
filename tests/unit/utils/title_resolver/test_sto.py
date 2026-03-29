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


def test_slug_from_query_prefers_precise_title_over_shared_token(
    monkeypatch,
) -> None:
    monkeypatch.setattr(tr, "CATALOG_SITES_LIST", ["aniworld.to", "s.to"])

    index_by_site = {
        "aniworld.to": {
            "the-ossan-newbie-adventurer": (
                "The Ossan Newbie Adventurer, Trained to Death by the Most "
                "Powerful Party, Became Invincible"
            ),
            "rick-and-morty-the-anime": "Rick and Morty: The Anime",
        },
        "s.to": {
            "the-rookie": "The Rookie",
            "rick-and-morty": "Rick and Morty",
        },
    }
    monkeypatch.setattr(tr, "load_or_refresh_index", lambda site: index_by_site[site])
    monkeypatch.setattr(tr, "load_or_refresh_alternatives", lambda _site: {})
    monkeypatch.setattr(tr, "_search_sto_slug", lambda _query: None)

    assert tr.slug_from_query("Rookie Le flic de Los Angeles") == (
        "s.to",
        "the-rookie",
    )
    assert tr.slug_from_query("Rick and Morty") == ("s.to", "rick-and-morty")


def test_slug_from_query_rejects_low_confidence_overlap(monkeypatch) -> None:
    monkeypatch.setattr(tr, "CATALOG_SITES_LIST", ["aniworld.to"])
    monkeypatch.setattr(
        tr,
        "load_or_refresh_index",
        lambda _site: {
            "the-ossan-newbie-adventurer": (
                "The Ossan Newbie Adventurer, Trained to Death by the Most "
                "Powerful Party, Became Invincible"
            )
        },
    )
    monkeypatch.setattr(tr, "load_or_refresh_alternatives", lambda _site: {})
    monkeypatch.setattr(tr, "_search_sto_slug", lambda _query: None)

    assert tr.slug_from_query("Rookie Le flic de Los Angeles") is None
