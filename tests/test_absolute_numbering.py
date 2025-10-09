from __future__ import annotations

from sqlmodel import Session

from app.db import (
    engine,
    list_episode_mappings_for_series,
)


def test_detect_absolute_identifiers():
    from app.utils.absolute_numbering import (
        is_absolute_identifier,
        parse_absolute_identifier,
    )

    assert is_absolute_identifier("001")
    assert is_absolute_identifier("12")
    assert parse_absolute_identifier("003") == 3
    assert parse_absolute_identifier("3") == 3
    assert parse_absolute_identifier("000") is None
    assert not is_absolute_identifier("S01E03")
    assert not is_absolute_identifier("1x03")
    assert parse_absolute_identifier("abc") is None


def test_resolve_absolute_episode_persists_and_skips_specials(client):
    from app.utils.absolute_numbering import resolve_absolute_episode

    catalog_calls = {"count": 0}

    def fetch_catalog():
        catalog_calls["count"] += 1
        return [
            {"absolute": 1, "season": 0, "episode": 1, "title": "Special"},
            {"absolute": 1, "season": 1, "episode": 1, "title": "Pilot"},
            {"absolute": 2, "season": 1, "episode": 2, "title": "Second"},
        ]

    with Session(engine) as session:
        mapping = resolve_absolute_episode(
            session,
            series_slug="series-a",
            absolute_number=1,
            fetch_catalog=fetch_catalog,
        )
        assert mapping is not None
        assert mapping.season_number == 1
        assert mapping.episode_number == 1
        # second call should reuse cached mapping without hitting catalog
        mapping_again = resolve_absolute_episode(
            session,
            series_slug="series-a",
            absolute_number=1,
            fetch_catalog=fetch_catalog,
        )
        assert mapping_again is not None
        assert catalog_calls["count"] == 1

        second = resolve_absolute_episode(
            session,
            series_slug="series-a",
            absolute_number=2,
            fetch_catalog=fetch_catalog,
        )
        assert second is not None
        assert second.episode_number == 2

        stored = list_episode_mappings_for_series(session, series_slug="series-a")
        assert len(stored) == 2
        assert all(row.season_number > 0 for row in stored)

        missing = resolve_absolute_episode(
            session,
            series_slug="series-a",
            absolute_number=99,
            fetch_catalog=lambda: [],
        )
        assert missing is None
