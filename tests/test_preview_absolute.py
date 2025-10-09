from __future__ import annotations

import xml.etree.ElementTree as ET

from sqlmodel import Session

from app.db import engine, upsert_episode_mapping


def test_search_preview_includes_absolute_identifier(client, monkeypatch):
    import app.api.torznab as tn

    monkeypatch.setattr(tn, "_slug_from_query", lambda q: "series-preview")
    monkeypatch.setattr(tn, "resolve_series_title", lambda slug: "Series Preview")

    with Session(engine) as session:
        upsert_episode_mapping(
            session,
            series_slug="series-preview",
            absolute_number=5,
            season_number=2,
            episode_number=1,
            episode_title="Episode Five",
        )

    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode: ["German Dub"],
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda slug, season, episode, language: (True, 1080, "h264", "prov", {}),
    )
    monkeypatch.setattr(
        tn,
        "build_release_name",
        lambda series_title, season, episode, absolute_number, height, vcodec, language: f"{series_title} ABS{absolute_number:03d}",
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title, slug, season, episode, language, provider, absolute_number=None: f"magnet:?xt=urn:btih:{slug}-{season}-{episode}&dn={title}&aw_slug={slug}&aw_s={season}&aw_e={episode}&aw_lang={language}&aw_abs={absolute_number}",
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "search", "q": "Series Preview 005", "sonarrAbsolute": "true"},
    )
    assert resp.status_code == 200

    root = ET.fromstring(resp.text)
    attr = root.find(
        ".//{http://torznab.com/schemas/2015/feed}attr[@name='absoluteNumber']"
    )
    assert attr is not None
    assert attr.get("value") == "5"
