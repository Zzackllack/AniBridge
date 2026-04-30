from __future__ import annotations

import xml.etree.ElementTree as ET

from sqlmodel import Session


def _seed_special_mapping_catalog(*, languages: list[str]) -> None:
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

    generation = "gen-special"
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
            slug="kaguya",
            title="Kaguya-sama",
            media_type_hint="series",
            relative_path="/anime/stream/kaguya",
            indexed_generation=generation,
        )
        replace_provider_catalog_aliases(
            session,
            provider="aniworld.to",
            slug="kaguya",
            aliases=["Kaguya-sama", "Kaguya"],
            indexed_generation=generation,
        )
        replace_provider_catalog_episodes(
            session,
            provider="aniworld.to",
            slug="kaguya",
            indexed_generation=generation,
            episodes=[
                {
                    "season": 0,
                    "episode": 4,
                    "relative_path": "/anime/stream/kaguya/filme/film-4",
                    "title_primary": "special title",
                    "title_secondary": None,
                    "media_type_hint": "episode",
                    "languages": [
                        {"language": language, "host_hints": ["VOE"]}
                        for language in languages
                    ],
                }
            ],
        )
        upsert_canonical_series(
            session,
            tvdb_id=12345,
            title="Kaguya-sama",
            imdb_id="tt0000001",
            aliases=["Kaguya"],
        )
        replace_canonical_episodes(
            session,
            tvdb_id=12345,
            episodes=[
                {"season": 0, "episode": 5, "title": "special title"},
            ],
        )
        replace_provider_series_mappings(
            session,
            provider="aniworld.to",
            slug="kaguya",
            indexed_generation=generation,
            mappings=[
                {
                    "tvdb_id": 12345,
                    "confidence": "confirmed",
                    "source": "title",
                    "rationale": "test",
                }
            ],
        )
        replace_provider_episode_mappings(
            session,
            provider="aniworld.to",
            slug="kaguya",
            indexed_generation=generation,
            mappings=[
                {
                    "provider_season": 0,
                    "provider_episode": 4,
                    "tvdb_id": 12345,
                    "canonical_season": 0,
                    "canonical_episode": 5,
                    "confidence": "confirmed",
                    "source": "special_alias",
                    "rationale": "test",
                }
            ],
        )
        session.commit()


def test_search_uses_special_mapping_alias_in_title(client):
    _seed_special_mapping_catalog(languages=["German Sub"])

    resp = client.get(
        "/torznab/api",
        params={"t": "search", "q": "Kaguya", "cat": "5070"},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    item = root.find("./channel/item")
    assert item is not None
    title = item.findtext("title") or ""
    assert "S00E05" in title
    enclosure = item.find("enclosure")
    assert enclosure is not None
    url = enclosure.get("url") or ""
    assert "aw_s=0" in url
    assert "aw_e=4" in url


def test_tvsearch_falls_back_to_special_mapping_when_requested_episode_missing(
    client,
) -> None:
    _seed_special_mapping_catalog(languages=["German Sub"])

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "Kaguya", "season": 0, "ep": 5, "cat": "5070"},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    item = root.find("./channel/item")
    assert item is not None
    title = item.findtext("title") or ""
    assert "S00E05" in title
    enclosure = item.find("enclosure")
    assert enclosure is not None
    url = enclosure.get("url") or ""
    assert "aw_s=0" in url
    assert "aw_e=4" in url


def test_tvsearch_reuses_resolved_special_mapping_across_languages(
    client, monkeypatch
) -> None:
    import app.api.torznab.api as torznab_api

    _seed_special_mapping_catalog(languages=["German Sub", "English Sub"])
    monkeypatch.setattr(torznab_api, "STRM_FILES_MODE", "no")

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "Kaguya", "season": 0, "ep": 5, "cat": "5070"},
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
    assert sum("aw_lang=German+Sub" in url for url in urls) == 1
    assert sum("aw_lang=English+Sub" in url for url in urls) == 1


def test_tvsearch_guid_alias_suffix_only_when_alias_differs(client) -> None:
    _seed_special_mapping_catalog(languages=["German Sub"])

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "Kaguya", "season": 0, "ep": 5, "cat": "5070"},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    item = root.find("./channel/item")
    assert item is not None
    guid = item.findtext("guid") or ""
    assert ":alias-s" not in guid
