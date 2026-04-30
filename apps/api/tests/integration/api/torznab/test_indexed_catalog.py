from __future__ import annotations

from sqlmodel import Session


def _seed_ready_catalog() -> None:
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

    generation = "gen-1"
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
            slug="kaguya-sama",
            title="Kaguya-sama",
            media_type_hint="series",
            relative_path="/anime/stream/kaguya-sama",
            indexed_generation=generation,
        )
        replace_provider_catalog_aliases(
            session,
            provider="aniworld.to",
            slug="kaguya-sama",
            aliases=["Kaguya-sama", "Kaguya"],
            indexed_generation=generation,
        )
        replace_provider_catalog_episodes(
            session,
            provider="aniworld.to",
            slug="kaguya-sama",
            indexed_generation=generation,
            episodes=[
                {
                    "season": 1,
                    "episode": 1,
                    "relative_path": "/anime/stream/kaguya-sama/staffel-1/episode-1",
                    "title_primary": "I Want To Be Invited To A Movie",
                    "title_secondary": None,
                    "media_type_hint": "episode",
                    "languages": [
                        {"language": "German Sub", "host_hints": ["VOE"]},
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
                {"season": 1, "episode": 1, "title": "I Want To Be Invited To A Movie"}
            ],
        )
        replace_provider_series_mappings(
            session,
            provider="aniworld.to",
            slug="kaguya-sama",
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
            slug="kaguya-sama",
            indexed_generation=generation,
            mappings=[
                {
                    "provider_season": 1,
                    "provider_episode": 1,
                    "tvdb_id": 12345,
                    "canonical_season": 1,
                    "canonical_episode": 1,
                    "confidence": "confirmed",
                    "source": "direct_numbering",
                    "rationale": "test",
                }
            ],
        )
        session.commit()


def test_search_returns_503_when_catalog_bootstrap_pending(client) -> None:
    from app.db import engine, upsert_provider_index_status

    with Session(engine) as session:
        upsert_provider_index_status(
            session,
            provider="aniworld.to",
            refresh_interval_hours=24.0,
            status="pending",
            bootstrap_completed=False,
        )

    response = client.get("/torznab/api", params={"t": "search", "q": "Kaguya"})

    assert response.status_code == 503
    assert "bootstrap" in response.json()["detail"].lower()


def test_search_test_result_bypasses_catalog_bootstrap(client, monkeypatch) -> None:
    import app.api.torznab.api as torznab_api

    monkeypatch.setattr(torznab_api, "TORZNAB_RETURN_TEST_RESULT", True)

    response = client.get("/torznab/api", params={"t": "search"})

    assert response.status_code == 200
    assert "<item>" in response.text


def test_search_uses_indexed_catalog_without_live_probe(client, monkeypatch) -> None:
    _seed_ready_catalog()
    monkeypatch.setattr(
        "app.utils.title_resolver.load_or_refresh_index",
        lambda site="aniworld.to": (_ for _ in ()).throw(
            AssertionError("unexpected live index refresh")
        ),
    )

    response = client.get("/torznab/api", params={"t": "search", "q": "Kaguya"})

    assert response.status_code == 200
    assert "Kaguya.sama.S01E01" in response.text
    assert "aw_slug=kaguya-sama" in response.text


def test_tvsearch_uses_indexed_canonical_mapping(client, monkeypatch) -> None:
    _seed_ready_catalog()
    monkeypatch.setattr(
        "app.utils.title_resolver.load_or_refresh_index",
        lambda site="aniworld.to": (_ for _ in ()).throw(
            AssertionError("unexpected live index refresh")
        ),
    )

    response = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "Kaguya", "season": 1, "ep": 1},
    )

    assert response.status_code == 200
    assert "Kaguya.sama.S01E01" in response.text
    assert "aw_s=1" in response.text
    assert "aw_e=1" in response.text
