from __future__ import annotations

import xml.etree.ElementTree as ET

from sqlmodel import Session


def _seed_ready_tv_catalog(
    *,
    canonical_title: str,
    query_aliases: list[str],
    provider_title: str | None = None,
    slug: str = "slug",
    tvdb_id: int = 12345,
    episode_mappings: list[tuple[int, int, int, int]] | None = None,
) -> None:
    from app.db import (
        engine,
        replace_canonical_episodes,
        replace_provider_catalog_aliases,
        replace_provider_catalog_episodes,
        replace_provider_catalog_title,
        replace_provider_episode_mappings,
        replace_provider_series_mappings,
        upsert_canonical_series,
        upsert_provider_index_status,
    )

    generation = f"gen-{slug}"
    mapped_episodes = episode_mappings or [(1, 1, 1, 1)]
    provider_title = provider_title or canonical_title

    with Session(engine) as session:
        for provider in ("aniworld.to", "s.to", "megakino"):
            upsert_provider_index_status(
                session,
                provider=provider,
                refresh_interval_hours=24.0,
                status="ready",
                current_generation=generation,
                latest_success_generation=generation,
                bootstrap_completed=True,
            )
        replace_provider_catalog_title(
            session,
            provider="aniworld.to",
            slug=slug,
            title=provider_title,
            media_type_hint="series",
            relative_path=f"/anime/stream/{slug}",
            indexed_generation=generation,
        )
        replace_provider_catalog_aliases(
            session,
            provider="aniworld.to",
            slug=slug,
            aliases=[provider_title, *query_aliases],
            indexed_generation=generation,
        )
        replace_provider_catalog_episodes(
            session,
            provider="aniworld.to",
            slug=slug,
            indexed_generation=generation,
            episodes=[
                {
                    "season": provider_season,
                    "episode": provider_episode,
                    "relative_path": f"/anime/stream/{slug}/staffel-{provider_season}/episode-{provider_episode}",
                    "title_primary": f"Episode {canonical_episode}",
                    "title_secondary": None,
                    "media_type_hint": "episode",
                    "languages": [
                        {"language": "German Sub", "host_hints": ["VOE"]},
                    ],
                }
                for provider_season, provider_episode, _canonical_season, canonical_episode in mapped_episodes
            ],
        )
        upsert_canonical_series(
            session,
            tvdb_id=tvdb_id,
            title=canonical_title,
            imdb_id=f"tt{tvdb_id:07d}",
            aliases=query_aliases,
        )
        replace_canonical_episodes(
            session,
            tvdb_id=tvdb_id,
            episodes=[
                {
                    "season": canonical_season,
                    "episode": canonical_episode,
                    "title": f"Episode {canonical_episode}",
                }
                for _provider_season, _provider_episode, canonical_season, canonical_episode in mapped_episodes
            ],
        )
        replace_provider_series_mappings(
            session,
            provider="aniworld.to",
            slug=slug,
            indexed_generation=generation,
            mappings=[
                {
                    "tvdb_id": tvdb_id,
                    "confidence": "confirmed",
                    "source": "title",
                    "rationale": "test",
                }
            ],
        )
        replace_provider_episode_mappings(
            session,
            provider="aniworld.to",
            slug=slug,
            indexed_generation=generation,
            mappings=[
                {
                    "provider_season": provider_season,
                    "provider_episode": provider_episode,
                    "tvdb_id": tvdb_id,
                    "canonical_season": canonical_season,
                    "canonical_episode": canonical_episode,
                    "confidence": "confirmed",
                    "source": "direct_numbering",
                    "rationale": "test",
                }
                for provider_season, provider_episode, canonical_season, canonical_episode in mapped_episodes
            ],
        )
        session.commit()


def test_caps(client):
    resp = client.get("/torznab/api", params={"t": "caps"})
    assert resp.status_code == 200
    ET.fromstring(resp.text)


def test_search(client):
    resp = client.get("/torznab/api", params={"t": "search", "q": "test"})
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.find("channel") is not None


def test_tvsearch_happy_path(client, monkeypatch):
    import app.api.torznab as tn

    _seed_ready_tv_catalog(canonical_title="Series", query_aliases=["foo"])
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected live probe")
        ),
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1, "ep": 1},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    item = root.find("./channel/item")
    assert item is not None
    seed = item.find("{http://torznab.com/schemas/2015/feed}attr[@name='seeders']")
    leech = item.find("{http://torznab.com/schemas/2015/feed}attr[@name='leechers']")
    lang_attr = item.find(
        "{http://torznab.com/schemas/2015/feed}attr[@name='language']"
    )
    subs_attr = item.find("{http://torznab.com/schemas/2015/feed}attr[@name='subs']")
    assert seed is not None and leech is not None
    assert lang_attr is not None and lang_attr.get("value") == "German"
    assert subs_attr is not None and subs_attr.get("value") == "German"


def test_tvsearch_empty(client):
    resp = client.get("/torznab/api", params={"t": "tvsearch", "q": "foo"})
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.find("./channel/item") is None


def test_tvsearch_uses_id_resolved_query_when_q_missing(client, monkeypatch):
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api_mod

    _seed_ready_tv_catalog(
        canonical_title="The Rookie",
        query_aliases=[],
        provider_title="The Rookie",
        slug="the-rookie",
        tvdb_id=350665,
    )
    monkeypatch.setattr(
        torznab_api_mod,
        "_resolve_tvsearch_query_from_ids",
        lambda **_kwargs: "The Rookie",
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected live probe")
        ),
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "season": 1, "ep": 1, "tvdbid": 350665},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.find("./channel/item") is not None


def test_tvsearch_season_search_emits_multiple_episodes(client, monkeypatch) -> None:
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api

    _seed_ready_tv_catalog(
        canonical_title="Series",
        query_aliases=["foo"],
        episode_mappings=[(1, 1, 1, 1), (1, 2, 1, 2), (1, 3, 1, 3)],
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected live probe")
        ),
    )
    monkeypatch.setattr(torznab_api, "STRM_FILES_MODE", "no")

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 3
    urls = [
        (
            item.find("enclosure").get("url")
            if item.find("enclosure") is not None
            else ""
        )
        for item in items
    ]
    assert any("aw_e=1" in url for url in urls)
    assert any("aw_e=2" in url for url in urls)
    assert any("aw_e=3" in url for url in urls)


def test_tvsearch_season_search_fallback_stops_on_consecutive_misses(
    client, monkeypatch
) -> None:
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api

    _seed_ready_tv_catalog(
        canonical_title="Series",
        query_aliases=["foo"],
        episode_mappings=[(1, 1, 1, 1), (1, 2, 1, 2)],
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected live probe")
        ),
    )
    monkeypatch.setattr(torznab_api, "STRM_FILES_MODE", "no")

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 2


def test_tvsearch_ep_zero_is_treated_as_season_search(client, monkeypatch) -> None:
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api

    _seed_ready_tv_catalog(
        canonical_title="Series",
        query_aliases=["foo"],
        episode_mappings=[(1, 1, 1, 1), (1, 2, 1, 2)],
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected live probe")
        ),
    )
    monkeypatch.setattr(torznab_api, "STRM_FILES_MODE", "no")

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1, "ep": 0},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 2
    urls = [
        (
            item.find("enclosure").get("url")
            if item.find("enclosure") is not None
            else ""
        )
        for item in items
    ]
    assert any("aw_e=1" in url for url in urls)
    assert any("aw_e=2" in url for url in urls)


def test_tvsearch_fast_season_mode_avoids_live_probe(client, monkeypatch) -> None:
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api

    _seed_ready_tv_catalog(
        canonical_title="Series",
        query_aliases=["foo"],
        episode_mappings=[(1, 1, 1, 1), (1, 2, 1, 2)],
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected live probe")
        ),
    )
    monkeypatch.setattr(torznab_api, "STRM_FILES_MODE", "no")

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 2


def test_tvsearch_season_search_limit_is_hard_item_cap(client, monkeypatch) -> None:
    import app.api.torznab.api as torznab_api

    monkeypatch.setattr(torznab_api, "STRM_FILES_MODE", "both")
    _seed_ready_tv_catalog(
        canonical_title="Series",
        query_aliases=["foo"],
        episode_mappings=[(1, 1, 1, 1), (1, 2, 1, 2)],
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1, "limit": 3},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 3
