"""Finite regression cases: evidence changes, ambiguity, budget and code rollback."""

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from catalog_core.identity import entity_id, mapping_id
from catalog_worker import canonical_cache, descriptors
from catalog_worker.aniworld import Link, Page
from catalog_worker.canonical import Enricher
from catalog_worker.correspondence import REASONS, summary
from catalog_worker.mapping import CanonicalEpisode, CanonicalTitle, match_title
from catalog_worker.state import State
from catalog_worker.state_migrations import preflight, rollback_matching
from catalog_worker.transport import Fetch

NOW = 1800000000


def seed(
    root: Path, provider: str = "aniworld.to", *, mapped: bool = True
) -> tuple[State, str]:
    state = State(root / (provider + ".sqlite"), provider)
    path = "/anime/stream/example" if provider == "aniworld.to" else "/serie/example"
    tid = state.discover(Link(path, "Example"), NOW)
    with state.db:
        state.db.execute("UPDATE title SET year=2020")
        state.db.execute("INSERT INTO mapping_input(title_id) VALUES(?)", (tid,))
        if mapped:
            state.db.execute(
                "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
                (
                    mapping_id(provider, tid, "tvdb", "123"),
                    tid,
                    "tvdb",
                    "123",
                    "skyhook-v1",
                    "reviewed",
                    NOW,
                ),
            )
    return state, tid


def episode(
    state: State,
    tid: str,
    season: int,
    number: int,
    name: str | None,
    aliases: tuple[str, ...] = (),
) -> str:
    path = (
        state.db.execute("SELECT path FROM title WHERE title_id=?", (tid,)).fetchone()[
            0
        ]
        + f"/staffel-{season}/episode-{number}"
    )
    with state.db:
        state.db.execute(
            "INSERT OR IGNORE INTO work(path,title_id,kind,due) VALUES(?,?,'episode',?)",
            (path, tid, NOW),
        )
    work = dict(state.db.execute("SELECT * FROM work WHERE path=?", (path,)).fetchone())
    state.detail(
        work,
        Page((), ("de-sub",), 0, None, episode_title=name, episode_aliases=aliases),
        NOW,
    )
    return entity_id(state.provider, path)


def test_unchanged_work_is_skipped_and_new_alias_rematches_without_fetch(tmp_path):
    state, tid = seed(tmp_path)
    eid = episode(state, tid, 9, 7, "A different wording")
    with state.db:
        canonical_cache.store(
            state,
            tid,
            "parent",
            "parent-matcher",
            NOW,
            [CanonicalEpisode(2, 3, "Verified alternate name", "777")],
        )
        assert canonical_cache.apply(state, tid, NOW) == "matched"
        row = dict(state.db.execute("SELECT * FROM matching_replay").fetchone())
        state.db.execute("UPDATE worker_meta SET dirty=0")
        assert canonical_cache.apply(state, tid, NOW + 1) == "unchanged"
        assert dict(state.db.execute("SELECT * FROM matching_replay").fetchone()) == row
        assert state.meta()["dirty"] == 0
    episode(state, tid, 9, 7, "A different wording", ("Verified alternate name",))
    with state.db:
        assert canonical_cache.reuse(state, tid, "parent", "parent-matcher", NOW + 2)
    assert tuple(
        state.db.execute(
            "SELECT season,episode,external_episode_id FROM canonical_episode WHERE entity_id=?",
            (eid,),
        ).fetchone()
    ) == (2, 3, "777")
    assert set(summary(state, tid)) <= REASONS
    state.close()


def test_translations_require_same_namespaced_id_and_coordinates():
    primary = [CanonicalEpisode(2, 4, "English", "99")]
    translated = [
        CanonicalEpisode(2, 4, "Wrong ID", "100"),
        CanonicalEpisode(3, 4, "Wrong season", "99"),
        CanonicalEpisode(2, 4, "Deutsch", "99"),
    ]
    assert descriptors.merge(primary, translated)[0].aliases == ("Deutsch",)
    assert (
        descriptors.merge([CanonicalEpisode(2, 4, "English")], translated)[0].aliases
        == ()
    )
    assert (
        descriptors.episodes(
            {
                "tvdbId": 123,
                "metadataSource": "tvdb",
                "episodes": [
                    {
                        "metadataShowId": 123,
                        "metadataId": 99,
                        "seasonNumber": 2,
                        "episodeNumber": 4,
                        "title": "Deutsch",
                    }
                ],
            }
        )[0].external_id
        == "99"
    )
    with pytest.raises(ValueError, match="parent mismatch"):
        descriptors.episodes(
            {
                "tvdbId": 123,
                "metadataSource": "tvdb",
                "episodes": [
                    {
                        "metadataShowId": 456,
                        "metadataId": 99,
                        "seasonNumber": 2,
                        "episodeNumber": 4,
                        "title": "Deutsch",
                    }
                ],
            }
        )


@pytest.mark.parametrize("provider", ["aniworld.to", "s.to"])
def test_unique_multilingual_name_maps_and_conflicting_alias_does_not(
    tmp_path, provider
):
    state, tid = seed(tmp_path, provider)
    positive = episode(
        state,
        tid,
        8,
        19,
        "An alternate English wording",
        ("Eine besondere Geschichte",),
    )
    conflict = episode(state, tid, 8, 20, "Other story", ("Ein anderes Ende",))
    rows = [
        CanonicalEpisode(
            1, 3, "Canonical English", "901", ("Eine besondere Geschichte",)
        ),
        CanonicalEpisode(1, 4, "Other story", "902"),
        CanonicalEpisode(1, 5, "Finale", "903", ("Ein anderes Ende",)),
    ]
    with state.db:
        canonical_cache.store(state, tid, "p", "m", NOW, rows)
        canonical_cache.apply(state, tid, NOW)
    assert tuple(
        state.db.execute(
            "SELECT season,episode FROM canonical_episode WHERE entity_id=?",
            (positive,),
        ).fetchone()
    ) == (1, 3)
    assert not state.db.execute(
        "SELECT 1 FROM canonical_episode WHERE entity_id=?", (conflict,)
    ).fetchone()
    assert summary(state, tid)["alias_conflict"] == 1
    state.close()


def test_repeated_names_need_independent_season_anchors(tmp_path):
    state, tid = seed(tmp_path)
    canonical = []
    repeats = []
    for native, target in [(8, 2), (9, 3)]:
        for n, name in enumerate(
            [
                f"Anchor {target} alpha",
                f"Anchor {target} beta",
                f"Anchor {target} gamma",
                "The return",
            ],
            1,
        ):
            eid = episode(state, tid, native, n, name)
            canonical.append(CanonicalEpisode(target, n + 10, name))
            if n == 4:
                repeats.append(eid)
    with state.db:
        canonical_cache.store(state, tid, "p", "m", NOW, canonical)
        assert summary(state, tid, contextual=False)["duplicate_source"] == 2
        canonical_cache.apply(state, tid, NOW)
    assert all(
        state.db.execute(
            "SELECT 1 FROM canonical_episode WHERE entity_id=?", (eid,)
        ).fetchone()
        for eid in repeats
    )
    state.close()


def test_changed_descriptor_never_repoints_existing_identity(tmp_path):
    state, tid = seed(tmp_path)
    eid = episode(state, tid, 8, 19, "Verified story")
    with state.db:
        canonical_cache.store(
            state, tid, "p", "m", NOW, [CanonicalEpisode(2, 3, "Verified story")]
        )
        canonical_cache.apply(state, tid, NOW)
        canonical_cache.store(
            state, tid, "p", "m", NOW + 1, [CanonicalEpisode(2, 4, "Verified story")]
        )
        assert canonical_cache.apply(state, tid, NOW + 1) == "conflict"
    assert tuple(
        state.db.execute(
            "SELECT season,episode FROM canonical_episode WHERE entity_id=?", (eid,)
        ).fetchone()
    ) == (2, 3)
    state.close()


def test_descriptor_shared_across_providers_and_budget_survives_restart(tmp_path):
    first, _tid1 = seed(tmp_path / "a", mapped=False)
    second, _tid2 = seed(tmp_path / "b", "s.to", mapped=False)
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2020,
            "tmdbId": 456,
            "episodes": [],
        }
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    enricher = Enricher({}, fetcher=fetch, clock=lambda: NOW, states=[first, second])
    assert asyncio.run(enricher.tick(first, NOW))
    assert len(calls) == 2
    assert asyncio.run(enricher.tick(second, NOW))
    assert len(calls) == 3 and enricher.last_work == "descriptor_reuse"
    assert (
        dict(second.db.execute("SELECT namespace,external_id FROM canonical_title"))[
            "tmdb-tv"
        ]
        == "456"
    )
    with first.db:
        first.db.executemany(
            "INSERT INTO canonical_request_start VALUES(?)", [(NOW,)] * 25
        )
    with second.db:
        second.db.execute("UPDATE mapping_input SET next_due=0")
        second.db.execute("DELETE FROM canonical_cache")
    restarted = Enricher({}, fetcher=fetch, clock=lambda: NOW, states=[first, second])
    assert not asyncio.run(restarted.tick(second, NOW))
    assert restarted.last_work == "admission_deferred" and len(calls) == 3
    first.close()
    second.close()


def test_retry_after_deadline_wins_over_matcher_changes_and_new_source(tmp_path):
    state, tid = seed(tmp_path, mapped=False)

    async def unavailable(*args, **kwargs):
        return Fetch("rate_limited", retry_after=7200, status=429)

    enricher = Enricher({}, fetcher=unavailable, clock=lambda: NOW)
    assert asyncio.run(enricher.tick(state, NOW))
    row = dict(state.db.execute("SELECT * FROM mapping_input").fetchone())
    assert row["next_due"] == NOW + 7200 and row["failures"] == 1
    with state.db:
        state.db.execute("UPDATE mapping_input SET matcher='old'")
    episode(state, tid, 1, 1, "New evidence")
    assert not asyncio.run(enricher.tick(state, NOW + 1))
    assert (
        state.db.execute("SELECT next_due FROM mapping_input").fetchone()[0]
        == NOW + 7200
    )
    state.close()


def test_v5_code_rollback_preserves_v4_observations_and_new_maps(tmp_path):
    state, tid = seed(tmp_path)
    episode(state, tid, 9, 7, "Verified story")
    with state.db:
        canonical_cache.store(
            state, tid, "p", "m", NOW, [CanonicalEpisode(2, 3, "Verified story")]
        )
        canonical_cache.apply(state, tid, NOW)
        state.db.execute(
            "UPDATE work SET failures=7,lease_until=?,due=?", (NOW + 10, NOW + 300)
        )
    tables = (
        "release",
        "canonical_episode",
        "work",
        "quarantine",
        "title_schedule",
        "signal_pending",
    )
    before = {
        table: [tuple(r) for r in state.db.execute(f"SELECT * FROM {table}")]
        for table in tables
    }
    state.close()
    filename = tmp_path / "aniworld.to.sqlite"
    rollback_matching(filename, "aniworld.to")
    assert preflight(filename, "aniworld.to") == 4
    with sqlite3.connect(filename) as db:
        assert {
            table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables
        } == before
    state = State(filename, "aniworld.to")
    assert preflight(filename, "aniworld.to") == 5
    assert {
        table: [tuple(r) for r in state.db.execute(f"SELECT * FROM {table}")]
        for table in tables
    } == before
    state.close()


def test_title_year_disambiguator_retains_year_kind_and_ambiguity():
    candidates = (CanonicalTitle("tvdb", "123", ("Example",), 2025, "series"),)
    assert match_title(("Example (2025)",), 2025, "series", candidates)
    assert not match_title(("Example (2024)",), 2025, "series", candidates)
    assert not match_title(("Example (2025)",), 2024, "series", candidates)
    assert not match_title(("Example (2025)",), 2025, "movie", candidates)
    assert not match_title(
        ("Example (2025)",),
        2025,
        "series",
        candidates + (CanonicalTitle("tvdb", "456", ("Example",), 2025, "series"),),
    )


def test_contraction_candidate_requires_three_independent_name_anchors(tmp_path):
    state, tid = seed(tmp_path)
    eid = episode(state, tid, 8, 21, "I'm going home")
    rows = [CanonicalEpisode(2, 9, "I am going home")]
    with state.db:
        canonical_cache.store(state, tid, "p", "m", NOW, rows)
        canonical_cache.apply(state, tid, NOW)
    assert not state.db.execute(
        "SELECT 1 FROM canonical_episode WHERE entity_id=?", (eid,)
    ).fetchone()
    for n, name in enumerate(
        ("A unique beginning", "A named adventure", "A distinct ending"), 1
    ):
        episode(state, tid, 8, n, name)
        rows.append(CanonicalEpisode(2, n, name))
    with state.db:
        canonical_cache.store(state, tid, "p", "m", NOW + 1, rows)
        canonical_cache.apply(state, tid, NOW + 1)
    assert tuple(
        state.db.execute(
            "SELECT season,episode FROM canonical_episode WHERE entity_id=?", (eid,)
        ).fetchone()
    ) == (2, 9)
    state.close()


def test_fresh_arrival_refresh_and_stable_wording_have_different_clocks(tmp_path):
    state, tid = seed(tmp_path)
    episode(state, tid, 8, 21, "Not yet in descriptor")
    assert canonical_cache.refresh_delay(state, tid, NOW) == 86400
    assert (
        canonical_cache.refresh_delay(state, tid, NOW + canonical_cache.TTL + 1)
        == canonical_cache.TTL
    )
    with state.db:
        canonical_cache.store(state, tid, "p", "m", NOW, [])
        assert not canonical_cache.reuse(state, tid, "p", "m", NOW + 86400)
        canonical_cache.store(
            state,
            tid,
            "p",
            "m",
            NOW + 86400,
            [CanonicalEpisode(2, 9, "Not yet in descriptor")],
        )
        canonical_cache.apply(state, tid, NOW + 86400)
    assert state.db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0] == 1
    state.close()


def test_stable_parse_gap_backoff_keeps_transient_http_recovery_distinct():
    from catalog_worker.retry import policy

    assert [policy("unexpected_structure", n, 0, None)[0] for n in range(8)] == [
        3600,
        7200,
        14400,
        28800,
        57600,
        86400,
        86400,
        86400,
    ]
    assert policy("transport_failure", 100, 0, None)[0] <= 360
    assert policy("rate_limited", 0, 0, 7200) == (7200, "blocked")


def test_v2_search_alias_proves_parent_and_translated_id_proves_episode(tmp_path):
    state, tid = seed(tmp_path, mapped=False)
    eid = episode(
        state, tid, 8, 19, "Different wording", ("Eine besondere Geschichte",)
    )
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        search = {
            "tvdbId": 123,
            "title": "Canonical group",
            "year": 2020,
            "alternativeTitles": [{"title": "Example"}],
        }
        detail = {
            "tvdbId": 123,
            "title": "Canonical group",
            "year": 2020,
            "metadataSource": "tvdb",
            "language": "deu" if "/deu/" in path else "eng",
            "episodes": [
                {
                    "metadataShowId": 123,
                    "metadataId": 777,
                    "seasonNumber": 2,
                    "episodeNumber": 3,
                    "title": "Eine besondere Geschichte"
                    if "/deu/" in path
                    else "Canonical wording",
                }
            ],
        }
        return Fetch(
            "ok", json.dumps([search] if "search" in path else detail).encode()
        )

    enricher = Enricher(
        {"episode_languages": ["deu"]}, fetcher=fetch, clock=lambda: NOW
    )
    assert asyncio.run(enricher.tick(state, NOW, title_id=tid))
    assert len(calls) == 3 and "/v2/tvdb/search" == calls[0]
    assert tuple(
        state.db.execute(
            "SELECT season,episode,external_episode_id FROM canonical_episode WHERE entity_id=?",
            (eid,),
        ).fetchone()
    ) == (2, 3, "777")
    # Force a local due probe; identical, verified inputs don't fetch or rematch.
    with state.db:
        state.db.execute("UPDATE mapping_input SET next_due=0")
    assert asyncio.run(enricher.tick(state, NOW + 1, title_id=tid))
    assert len(calls) == 3
    state.close()


def test_shared_imdb_with_conflicting_cut_year_cannot_create_parent(tmp_path):
    state, _tid = seed(tmp_path, mapped=False)
    with state.db:
        state.db.execute("UPDATE mapping_input SET explicit_imdb='tt1234567'")

    async def fetch(origin, path, **kwargs):
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2006 if "shows" in path else 2020,
            "imdbId": "tt1234567",
            "episodes": [],
        }
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    assert asyncio.run(Enricher({}, fetcher=fetch, clock=lambda: NOW).tick(state, NOW))
    assert not state.db.execute("SELECT 1 FROM canonical_title").fetchone()
    assert (
        state.db.execute("SELECT outcome FROM mapping_input").fetchone()[0]
        == "conflict"
    )
    state.close()


def test_malformed_canonical_ids_and_coordinates_reject_whole_descriptor():
    row = {
        "metadataShowId": 123,
        "metadataId": 777,
        "seasonNumber": 2,
        "episodeNumber": 3,
        "title": "A verified story",
    }
    for wrong in ({**row, "episodeNumber": 4}, {**row, "metadataId": 778}):
        with pytest.raises(ValueError, match="conflicting canonical episode"):
            descriptors.episodes(
                {"tvdbId": 123, "metadataSource": "tvdb", "episodes": [row, wrong]}
            )


def test_redirect_budget_deferral_is_local_and_survives_restart(tmp_path):
    state, _tid = seed(tmp_path, mapped=False)

    async def fetch(origin, path, **kwargs):
        for _ in range(6):
            await kwargs["before_request"]()
        raise AssertionError("redirect must exhaust local budget")

    with state.db:
        state.db.executemany(
            "INSERT INTO canonical_request_start VALUES(?)", [(NOW,)] * 26
        )
    before = dict(state.db.execute("SELECT * FROM mapping_input").fetchone())
    enricher = Enricher({}, fetcher=fetch, clock=lambda: NOW, states=[state])
    assert not asyncio.run(enricher.tick(state, NOW))
    assert enricher.last_work == "admission_deferred"
    assert dict(state.db.execute("SELECT * FROM mapping_input").fetchone()) == before
    assert (
        Enricher({}, fetcher=fetch, clock=lambda: NOW, states=[state]).request_count(
            NOW
        )
        == 30
    )
    state.close()


def test_verified_translation_supplies_name_for_unnamed_english_episode(tmp_path):
    state, tid = seed(tmp_path)
    eid = episode(state, tid, 8, 19, "Eine besondere Geschichte")
    en = {
        "tvdbId": 123,
        "metadataSource": "tvdb",
        "episodes": [
            {
                "metadataShowId": 123,
                "metadataId": 777,
                "seasonNumber": 2,
                "episodeNumber": 3,
                "title": None,
            }
        ],
    }
    de = {
        **en,
        "episodes": [{**en["episodes"][0], "title": "Eine besondere Geschichte"}],
    }
    primary = descriptors.episodes(en)
    assert primary[0].title == "" and primary[0].external_id == "777"
    with state.db:
        canonical_cache.store(
            state,
            tid,
            "p",
            "m",
            NOW,
            descriptors.merge(primary, descriptors.episodes(de)),
        )
        canonical_cache.apply(state, tid, NOW)
    assert tuple(
        state.db.execute(
            "SELECT season,episode,external_episode_id FROM canonical_episode WHERE entity_id=?",
            (eid,),
        ).fetchone()
    ) == (2, 3, "777")
    state.close()


def test_annotations_cannot_turn_generic_numbers_into_name_evidence(tmp_path):
    from catalog_worker.episode_matching import source_keys

    assert source_keys("Episode 40 [Episode 240]", "aniworld.to") == ()
    assert source_keys("(Episode 40 / Episode 240)", "s.to") == ()
    assert source_keys("Episode-40", "aniworld.to") == ()
    state, tid = seed(tmp_path)
    eid = episode(state, tid, 8, 19, "Episode 40 [Episode 240]")
    with state.db:
        canonical_cache.store(
            state, tid, "p", "m", NOW, [CanonicalEpisode(1, 40, "Episode 40")]
        )
        canonical_cache.apply(state, tid, NOW)
    assert not state.db.execute(
        "SELECT 1 FROM canonical_episode WHERE entity_id=?", (eid,)
    ).fetchone()
    assert canonical_cache.refresh_delay(state, tid, NOW) == canonical_cache.TTL
    state.close()


def test_translated_aliases_of_one_episode_are_only_one_context_anchor(tmp_path):
    from catalog_worker.episode_matching import infer_seasons

    state, tid = seed(tmp_path)
    episode(state, tid, 9, 1, "One anchor", ("Ein Anker", "Un ancrage"))
    with state.db:
        canonical_cache.store(
            state,
            tid,
            "p",
            "m",
            NOW,
            [CanonicalEpisode(2, 8, "One anchor", "77", ("Ein Anker", "Un ancrage"))],
        )
    assert infer_seasons(state, tid) == {}
    state.close()


def test_reviewed_cohort_wording_pairs_keep_canonical_ids_and_native_coordinates(
    tmp_path,
):
    """Metadata fixture regression; population accuracy is evaluated on copied state."""
    from itertools import groupby

    fixture = json.loads(
        (Path(__file__).parent / "fixtures/mapping-cohort-2026-10-14.json").read_text()
    )
    positives = sorted(
        (r for r in fixture["cases"] if r["label"] == "positive"),
        key=lambda r: (r["provider"], r["title_id"]),
    )
    for index, ((provider, _), rows) in enumerate(
        groupby(positives, key=lambda r: (r["provider"], r["title_id"]))
    ):
        rows = list(rows)
        directory = tmp_path / str(index)
        directory.mkdir()
        state, tid = seed(directory, provider)
        ids, canonical = [], []
        for row in rows:
            ids.append(
                episode(
                    state,
                    tid,
                    *row["native"],
                    row["source_name"],
                    tuple(row["source_aliases"]),
                )
            )
            expected = row["expected"]
            names = tuple(e["name"] for e in row["canonical_evidence"])
            canonical.append(
                CanonicalEpisode(
                    expected["season"],
                    expected["episode"],
                    names[0],
                    expected["tvdb_episode_id"],
                    names[1:],
                )
            )
        with state.db:
            canonical_cache.store(state, tid, "fixture", "reviewed", NOW, canonical)
            canonical_cache.apply(state, tid, NOW)
        for eid, row in zip(ids, rows, strict=True):
            found = state.db.execute(
                "SELECT season,episode,external_episode_id FROM canonical_episode WHERE entity_id=?",
                (eid,),
            ).fetchone()
            assert tuple(found) == (
                row["expected"]["season"],
                row["expected"]["episode"],
                row["expected"]["tvdb_episode_id"],
            )
            native = state.db.execute(
                "SELECT native_season,native_episode FROM entity WHERE entity_id=?",
                (eid,),
            ).fetchone()
            assert tuple(native) == tuple(row["native"])
        state.close()
