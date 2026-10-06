import asyncio
import json

from catalog_core.identity import entity_id, title_id
from catalog_worker.aniworld import Link, Page, parse
from catalog_worker.canonical import Enricher
from catalog_worker.state import State
from catalog_worker.transport import Fetch

NOW = 1800000000
TITLE = "/anime/stream/example"


def ready(tmp_path, year=2020, imdb=None):
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    state.listing(Page((Link(TITLE, "Example"),), (), 0, None), NOW)
    state.detail(
        state.claim(NOW),
        Page(
            (Link(TITLE + "/staffel-1", "Season"),),
            (),
            0,
            "Example",
            year=year,
            explicit_imdb=imdb,
        ),
        NOW,
    )
    return state


def test_provider_metadata_keeps_year_and_explicit_id_only():
    page = parse(
        b'<html><body><h1 data-alternativetitles="Other, Another">Example</h1><span itemprop="startDate"><a href="https://aniworld.to/animes/jahr/2020">2020</a></span><a data-imdb="tt1234567" href="https://www.imdb.com/title/tt1234567">IMDB</a><a href="/anime/stream/example/staffel-1">Season 1</a></body></html>',
        "detail",
    )
    assert (page.year, page.explicit_imdb, page.aliases) == (
        2020,
        "tt1234567",
        ("Other", "Another"),
    )
    assert "imdb.com" not in repr(page)


def test_enrichment_persists_compact_outcome_without_ordinal_mapping(tmp_path):
    state = ready(tmp_path)
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2020,
            "episodes": [{"seasonNumber": 1, "episodeNumber": 1, "title": "One"}],
        }
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    enricher = Enricher({}, fetcher=fetch)
    assert asyncio.run(enricher.tick(state, NOW))
    assert len(calls) == 2
    row = state.db.execute("SELECT * FROM canonical_title").fetchone()
    assert row["external_id"] == "123" and row["evidence"] == "exact_title_year"
    assert not state.db.execute("SELECT 1 FROM canonical_episode").fetchone()
    assert not asyncio.run(enricher.tick(state, NOW + 1))
    # A normal unchanged listing does not reset the mapping cadence.
    state.listing(Page((Link(TITLE, "Example"),), (), 0, None), NOW + 2)
    assert not asyncio.run(enricher.tick(state, NOW + 2))
    state.close()


def test_missing_year_and_ambiguous_results_stay_unresolved(tmp_path):
    state = ready(tmp_path, year=None)
    calls = []

    async def fetch(*args, **kwargs):
        calls.append(1)
        return Fetch(
            "ok",
            json.dumps(
                [
                    {"tvdbId": 1, "title": "Example", "year": 2020},
                    {"tvdbId": 2, "title": "Example", "year": 2020},
                ]
            ).encode(),
        )

    enricher = Enricher({}, fetcher=fetch)
    asyncio.run(enricher.tick(state, NOW))
    assert calls == []
    with state.db:
        state.db.execute("UPDATE title SET year=2020")
        state.db.execute("UPDATE mapping_input SET next_due=0")
    asyncio.run(enricher.tick(state, NOW + 1))
    assert len(calls) == 1
    assert not state.db.execute("SELECT 1 FROM canonical_title").fetchone()
    state.close()


def test_local_request_budget_defers_without_recording_source_failure(tmp_path):
    state = ready(tmp_path)
    clock = [NOW]
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        item = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    enricher = Enricher({}, fetcher=fetch, clock=lambda: clock[0])
    enricher.starts.extend([NOW] * 28)
    previous = dict(state.db.execute("SELECT * FROM mapping_input").fetchone())
    assert not asyncio.run(enricher.tick(state, NOW))
    assert calls == []
    assert dict(state.db.execute("SELECT * FROM mapping_input").fetchone()) == previous

    clock[0] += 60
    assert asyncio.run(enricher.tick(state, clock[0]))
    assert len(calls) == 2
    result = state.db.execute("SELECT * FROM mapping_input").fetchone()
    assert result["outcome"] == "matched" and result["failures"] == 0
    state.close()


def test_explicit_id_must_match_search_and_detail(tmp_path):
    state = ready(tmp_path, year=None, imdb="tt1234567")

    async def fetch(origin, path, **kwargs):
        item = {
            "tvdbId": 123,
            "title": "Different localized name",
            "imdbId": "tt1234567" if "search" in path else "tt9999999",
        }
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    asyncio.run(Enricher({}, fetcher=fetch).tick(state, NOW))
    assert not state.db.execute("SELECT 1 FROM canonical_title").fetchone()
    assert (
        state.db.execute(
            "SELECT outcome FROM mapping_input WHERE title_id=?",
            (title_id("aniworld.to", TITLE),),
        ).fetchone()[0]
        == "source_failure"
    )
    state.close()


def test_reviewed_season_requires_known_mapping_and_compare_and_swap(tmp_path):
    import pytest
    from catalog_worker.review import season

    state = ready(tmp_path)
    state.detail(
        state.claim(NOW),
        Page((Link(TITLE + "/staffel-1/episode-1", "One"),), (), 0, None),
        NOW,
    )
    state.detail(
        state.claim(NOW), Page((), ("de-dub",), 0, "Example", episode_title="One"), NOW
    )
    tid = title_id("aniworld.to", TITLE)
    body = {
        "title_id": tid,
        "namespace": "tvdb",
        "external_id": "123",
        "native_season": 1,
        "canonical_season": 2,
        "expected_old": None,
    }
    with pytest.raises(ValueError, match="validated title"):
        season(state, body)

    async def fetch(origin, path, **kwargs):
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2020,
            "episodes": [{"seasonNumber": 2, "episodeNumber": 4, "title": "One"}],
        }
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    enricher = Enricher({}, fetcher=fetch)
    asyncio.run(enricher.tick(state, NOW))
    season(state, body)
    asyncio.run(enricher.tick(state, NOW + 1))
    mapped = state.db.execute("SELECT season,episode FROM canonical_episode").fetchone()
    assert tuple(mapped) == (2, 4)
    with pytest.raises(ValueError, match="correspondence changed"):
        season(state, {**body, "canonical_season": 3})
    season(state, {**body, "expected_old": 2, "canonical_season": 3})
    assert state.db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0] == 0
    assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] > 0
    state.close()


def test_private_episode_cache_reuses_series_after_language_and_entity_changes(
    tmp_path,
):
    from catalog_core.providers.recent import Change, Window
    from catalog_worker.review import season
    from catalog_worker.signals import Signals

    state = ready(tmp_path)
    state.detail(
        state.claim(NOW),
        Page((Link(TITLE + "/staffel-1/episode-1", "One"),), (), 0, None),
        NOW,
    )
    state.detail(
        state.claim(NOW), Page((), ("de-sub",), 0, None, episode_title="One"), NOW
    )
    calls = []
    item = {
        "tvdbId": 123,
        "title": "Example",
        "year": 2020,
        "episodes": [
            {"seasonNumber": 1, "episodeNumber": 1, "title": "One"},
            {"seasonNumber": 1, "episodeNumber": 2, "title": "Two"},
        ],
    }

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    enricher = Enricher({}, fetcher=fetch)
    asyncio.run(enricher.tick(state, NOW))
    assert len(calls) == 2
    season(
        state,
        {
            "title_id": title_id("aniworld.to", TITLE),
            "namespace": "tvdb",
            "external_id": "123",
            "native_season": 1,
            "canonical_season": 1,
            "expected_old": None,
        },
    )
    episode = TITLE + "/staffel-1/episode-2"
    Signals(state).accept(
        Window((Change(episode, "Example", "de-sub"),), 0), NOW + 1, 900
    )
    # Complete missing season metadata before its targeted episode.
    while work := state.claim(NOW + 1, incremental=True):
        state.detail(work, Page((), ("de-sub",), 0, None, episode_title="Two"), NOW + 1)
        Signals(state).settle(work, NOW + 1, success=True)
    asyncio.run(enricher.tick(state, NOW + 1))
    assert len(calls) == 2
    assert tuple(
        state.db.execute(
            "SELECT season,episode,checked_at FROM canonical_episode WHERE entity_id=?",
            (entity_id("aniworld.to", episode),),
        ).fetchone()
    ) == (1, 2, NOW)
    with state.db:
        state.db.execute("UPDATE mapping_input SET next_due=0")
    state.close()
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    asyncio.run(Enricher({}, fetcher=fetch).tick(state, NOW + 2))
    assert len(calls) == 2
    # Expiry refreshes the already validated series once, without repeating searches.
    with state.db:
        state.db.execute("UPDATE mapping_input SET next_due=0")
    asyncio.run(Enricher({}, fetcher=fetch).tick(state, NOW + 604801))
    assert len(calls) == 3 and "/shows/" in calls[-1]
    state.close()


def test_cached_ambiguous_names_and_unreviewed_seasons_never_map(tmp_path):
    from catalog_worker import canonical_cache
    from catalog_worker.mapping import CanonicalEpisode

    state = ready(tmp_path)
    tid = title_id("aniworld.to", TITLE)
    with state.db:
        canonical_cache.store(
            state,
            tid,
            "digest",
            "matcher",
            NOW,
            [CanonicalEpisode(1, 1, "Same"), CanonicalEpisode(1, 2, "Same")],
        )
    assert state.db.execute("SELECT episode FROM canonical_hint").fetchone()[0] is None
    assert canonical_cache.apply(state, tid, NOW) == "matched"
    assert not state.db.execute("SELECT 1 FROM canonical_episode").fetchone()
    state.close()
