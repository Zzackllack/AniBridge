from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest


class _Availability:
    available = True
    is_fresh = True
    height = 1080
    vcodec = "h264"
    provider = "prov"


@pytest.fixture
def availability_record():
    return _Availability()


def test_tvsearch_absolute_converts_episode_indices(client, monkeypatch, availability_record):
    import app.api.torznab as tn
    from app.utils import absolute_numbering as absmap

    monkeypatch.setattr(tn, "_slug_from_query", lambda q: "series-abs")
    monkeypatch.setattr(tn, "resolve_series_title", lambda slug: "Series ABS")

    monkeypatch.setattr(
        absmap,
        "fetch_episode_catalog",
        lambda slug: [
            {"absolute": 5, "season": 2, "episode": 1, "title": "Episode 5"},
            {"absolute": 6, "season": 2, "episode": 2, "title": "Episode 6"},
        ],
    )

    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode: ["German Dub"],
    )
    monkeypatch.setattr(
        tn,
        "get_availability",
        lambda session, slug, season, episode, language: availability_record,
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda slug, season, episode, language: (True, 1080, "h264", "prov", {}),
    )

    captured = {}

    def fake_release_name(series_title, season, episode, height, vcodec, language):
        captured.setdefault("release_calls", []).append((season, episode))
        return f"{series_title} S{season:02d}E{episode:02d}"

    def fake_magnet(title, slug, season, episode, language, provider):
        captured.setdefault("magnet_calls", []).append((season, episode))
        return f"magnet:?xt=urn:btih:{slug}-{season}-{episode}"

    monkeypatch.setattr(tn, "build_release_name", fake_release_name)
    monkeypatch.setattr(tn, "build_magnet", fake_magnet)

    resp = client.get(
        "/torznab/api",
        params={
            "t": "tvsearch",
            "q": "Series ABS",
            "season": 1,
            "ep": 5,
            "sonarrAbsolute": "true",
        },
    )
    assert resp.status_code == 200

    root = ET.fromstring(resp.text)
    attr = root.find(
        ".//{http://torznab.com/schemas/2015/feed}attr[@name='absoluteNumber']"
    )
    assert attr is not None
    assert attr.get("value") == "5"

    assert captured["release_calls"] == [(2, 1)]
    assert captured["magnet_calls"] == [(2, 1)]


def test_tvsearch_absolute_fallback_returns_catalog(
    client, monkeypatch, availability_record, caplog
):
    import app.api.torznab as tn
    from app.utils import absolute_numbering as absmap
    import app.config as config

    caplog.set_level("INFO")

    monkeypatch.setattr(tn, "_slug_from_query", lambda q: "series-fallback")
    monkeypatch.setattr(tn, "resolve_series_title", lambda slug: "Series Fallback")

    monkeypatch.setattr(
        absmap,
        "fetch_episode_catalog",
        lambda slug: [
            {"absolute": 1, "season": 1, "episode": 1, "title": "Episode 1"},
            {"absolute": 2, "season": 1, "episode": 2, "title": "Episode 2"},
            {"absolute": 100, "season": 0, "episode": 1, "title": "Special"},
        ],
    )

    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode: ["German Dub"],
    )
    monkeypatch.setattr(
        tn,
        "get_availability",
        lambda session, slug, season, episode, language: availability_record,
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda slug, season, episode, language: (True, 1080, "h264", "prov", {}),
    )
    monkeypatch.setattr(
        tn,
        "build_release_name",
        lambda series_title, season, episode, height, vcodec, language: f"{series_title} S{season:02d}E{episode:02d}",
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title, slug, season, episode, language, provider: f"magnet:?xt=urn:btih:{slug}-{season}-{episode}",
    )

    monkeypatch.setattr(config, "ANIBRIDGE_FALLBACK_ALL_EPISODES", True)

    resp = client.get(
        "/torznab/api",
        params={
            "t": "tvsearch",
            "q": "Series Fallback",
            "season": 1,
            "ep": 99,
            "sonarrAbsolute": "true",
        },
    )
    assert resp.status_code == 200

    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 2  # specials excluded

    log_text = "\n".join(record.message for record in caplog.records)
    assert "cannot map episode" in log_text
    assert "using fallback" in log_text
